#!/usr/bin/env python3
"""CANAL+ playback worker. Only sanitized events leave this process."""
import argparse
import base64
import contextlib
import io
import json
import os
import queue
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import xml.etree.ElementTree as ET

import canal_channels_test as channels
import canal_drm_demo as drm
import canal_stream_test_v2 as stream
import player_runtime as runtime
from version import APP_VERSION

STOP = threading.Event()
REPORT = Path("/tmp/canal_e2_playback_report.json")
state = {"prototype_version": APP_VERSION, "account_tokens_printed": False,
         "drm_keys_printed": False, "drm_keys_saved": False,
         "video_playback_confirmed_by_user": False}


def emit(stage, **details):
    state.update(stage=stage, **details)
    # Only locally constructed status fields are persisted, never player output.
    channels.atomic_private_json(REPORT, state)
    output = sys.__stdout__
    output.write(json.dumps({"stage": stage, **details}, ensure_ascii=False) + "\n")
    output.flush()


def collect_keys(target, keys):
    for item in keys:
        if item.type == "CONTENT" and len(item.kid) == 16 and len(item.key) == 16:
            target[bytes(item.kid).hex()] = bytes(item.key).hex()


def acquire_track_keys(directory, http, selected, out, ids, video, audio, keys, license_request=None):
    requested = set()
    for track in (video, audio):
        if not track["encrypted"]:
            continue
        if not track["kids"]:
            raise stream.StreamError("encrypted_initialization_missing_key_id")
        for pssh in track["pssh"][:4]:
            if track["kids"] <= keys.keys():
                break
            if pssh in requested:
                continue
            requested.add(pssh)
            stream.check_license(directory, drm, http, pssh, selected, out, ids,
                                 key_callback=lambda values: collect_keys(keys, values),
                                 license_request=license_request)
    summary = {"license_request_count": len(requested), "content_key_count": len(keys)}
    for label, track in (("video", video), ("audio", audio)):
        summary.update({
            label + "_encrypted": track["encrypted"],
            label + "_manifest_kid_count": len(track["manifest_kids"]),
            label + "_init_kid_count": len(track["kids"]),
            label + "_init_pssh_count": track["init_pssh_count"],
            label + "_key_match_count": len(track["kids"] & keys.keys()),
            label + "_manifest_ids_match_init": track["manifest_kids"] == track["kids"],
        })
    return summary


class ManifestServer(ThreadingHTTPServer):
    daemon_threads = True


def start_manifest_server(mpd_url, root, height, on_error, video_reference=None):
    initial, expected = runtime.filtered_manifest(root, mpd_url, height, video_reference=video_reference)
    endpoint = "/" + secrets.token_hex(16) + "/manifest.mpd"
    first = [initial]
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path != endpoint:
                self.send_error(404)
                return
            try:
                with lock:
                    if first:
                        body = first.pop()
                    else:
                        raw, final = stream.Http().read(mpd_url)
                        current = ET.fromstring(raw)
                        body, _ = runtime.filtered_manifest(current, final, height, expected, video_reference)
                self.send_response(200)
                self.send_header("Content-Type", "application/dash+xml")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as error:
                reason = error.reason if isinstance(error, stream.StreamError) else "manifest_refresh_failed"
                on_error(reason)
                self.send_error(503)

    server = ManifestServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, "http://127.0.0.1:%d%s" % (server.server_port, endpoint)


def stop_player(player):
    if player is None or player.poll() is not None:
        return
    try:
        player.stdin.write(b"q\n")
        player.stdin.flush()
    except (BrokenPipeError, OSError):
        pass
    try:
        player.wait(timeout=4)
    except subprocess.TimeoutExpired:
        player.terminate()
        try:
            player.wait(timeout=2)
        except subprocess.TimeoutExpired:
            player.kill()
            player.wait(timeout=2)


def player_events(pipe, events):
    # Native FFmpeg logs can contain stream URLs and keys. Never forward them.
    try:
        for line in iter(lambda: pipe.readline(65537), b""):
            if len(line) > 65536 or not line.startswith(b"{"):
                continue
            try:
                value = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if not isinstance(value, dict):
                continue
            for label in ("PLAYBACK_OPEN", "OUTPUT_OPEN", "PLAYBACK_PLAY", "PLAYBACK_STOP",
                          "PLAYBACK_PAUSE", "PLAYBACK_CONTINUE", "PLAYBACK_SEEK"):
                item = value.get(label)
                if isinstance(item, dict) and isinstance(item.get("sts"), int):
                    events.put((label.lower(), item["sts"]))
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--channel")
    source.add_argument("--vod")
    parser.add_argument("--height", type=int, default=1080)
    args = parser.parse_args()
    if ((args.channel is not None and not re.fullmatch(r"[0-9]{1,12}", args.channel))
            or (args.vod is not None and not re.fullmatch(r"[0-9]{1,15}(?:_[0-9]{1,10})?", args.vod))
            or not 1 <= args.height <= 4320):
        return 2
    def interrupt(*_):
        STOP.set()
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    player, server, keys, vod_api = None, None, {}, None
    events = queue.Queue()
    try:
        emit("prepare")
        binary = runtime.ensure_player(Path("/var/lib/canal-e2"), emit)
        if STOP.is_set():
            return 0
        emit("refresh_channels" if not args.vod else "vod_check_access")
        session_path = Path("/etc/canal-e2/session.json")
        saved = channels.load_json(session_path)
        auth = saved.get("authentication", {})
        if not isinstance(auth, dict) or not isinstance(auth.get("passToken"), str):
            raise stream.StreamError("authenticated_session_missing")
        http = stream.Http()
        license_request = None
        if args.vod:
            from vod_api import VodApi
            vod_api = VodApi(auth, saved.get("device_id"))
            emit("vod_resolve_stream")
            root, mpd_url, licence_url = vod_api.resolve(args.vod)
            license_request = lambda challenge: vod_api.licence(licence_url, challenge)
            selected, out, ids = {}, {}, {}
        else:
            ids = channels.get_client_ids(session_path.with_name("client.json"))
            response = channels.fetch_init(channels.make_request(auth["passToken"], ids))
            out = channels.extract_outdata(response)
            entries = channels.normalize_channels(out)
            selected = stream.select_channel(entries, args.channel)
            channels.atomic_private_json(session_path.with_name("live.json"), {
                "schema_version": 1, "client_ids": ids,
                "init_live_response": response, "channels": entries})
            emit("resolve_stream", channel=selected["name"])
            root, mpd_url = stream.resolve_mpd(http, stream.entry_url(selected, out))
        video, audio = runtime.select_tracks(root, args.height)
        emit("inspect_initialization", requested_max_height=args.height, selected_video_height=video["height"],
             selected_audio_language=audio["lang"] if audio["lang"] in ("pl", "pol", "pl-pl", "en", "eng", "und", "") else "other")
        runtime.inspect_track_initialization(http, video, mpd_url)
        runtime.inspect_track_initialization(http, audio, mpd_url)
        emit("license", video_init_encrypted=video["encrypted"], audio_init_encrypted=audio["encrypted"])
        cache = Path("/var/lib/canal-e2")
        import tempfile
        with tempfile.TemporaryDirectory(prefix="drm-stage-", dir=cache) as temporary:
            directory = Path(temporary)
            # Suppress both Python logs and public engine diagnostic printing.
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                drm.prepare_engine(directory)
                mapping = acquire_track_keys(directory, http, selected, out, ids, video, audio, keys,
                                             license_request=license_request)
        emit("key_mapping", **mapping)
        if not keys and (video["encrypted"] or audio["encrypted"]):
            raise stream.StreamError("license_has_no_content_keys")
        options = runtime.licensed_video_options(root, args.height, keys.keys())
        emit("check_video_quality", licensed_video_heights=sorted({item["height"] for item in options}))
        if video["kids"] - keys.keys():
            replacement = None
            for candidate in options:
                # MPD is a candidate index; always verify the actual selected init.
                runtime.inspect_track_initialization(http, candidate, mpd_url)
                if candidate["kids"] <= keys.keys():
                    replacement = candidate
                    break
            if replacement is None:
                raise stream.StreamError("no_granted_video_key_for_available_qualities")
            video = replacement
            emit("quality_selected", selected_video_height=video["height"],
                 video_key_match_count=len(video["kids"] & keys.keys()),
                 video_manifest_kid_count=len(video["manifest_kids"]),
                 video_init_kid_count=len(video["kids"]), video_init_pssh_count=video["init_pssh_count"],
                 video_manifest_ids_match_init=video["manifest_kids"] == video["kids"],
                 quality_fallback=True)
        if (video["kids"] | audio["kids"]) - keys.keys():
            raise stream.StreamError("selected_audio_or_video_key_missing")
        emit("license_ok", content_key_count=len(keys), selected_video_height=video["height"])
        if STOP.is_set():
            return 0
        server, manifest_url = start_manifest_server(mpd_url, root, args.height,
                                                    lambda reason: events.put((reason, None)),
                                                    video_reference=runtime.track_reference(video))
        environment = os.environ.copy()
        environment["LD_LIBRARY_PATH"] = str(binary.parent.parent / "lib")
        # FFmpeg dictionary syntax: kid=key:kid=key. Keys stay in process memory;
        # never write a playlist, decrypted file or native player log.
        key_map = ":".join(kid + "=" + key for kid, key in sorted(keys.items()))
        command = [str(binary), manifest_url]
        if keys:
            command.extend(["-f", "cenc_decryption_keys=" + key_map])
        command.extend(["-u", "Mozilla/5.0", "-h", "Origin: https://www.canalplus.com\r\nReferer: https://www.canalplus.com/\r\n",
                        "-e", "-3", "-s"])
        emit("starting_player")
        try:
            player = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, env=environment, bufsize=0)
        except OSError:
            raise stream.StreamError("private_player_start_failed") from None
        for pipe in (player.stdout, player.stderr):
            threading.Thread(target=player_events, args=(pipe, events), daemon=True).start()
        if args.vod:
            def read_controls():
                for line in sys.stdin:
                    command = line.strip()
                    if command in ("pause", "resume", "seek_back", "seek_forward"):
                        events.put(("control_" + command, 0))
            threading.Thread(target=read_controls, daemon=True).start()
        started = time.monotonic()
        playing = False
        while not STOP.is_set():
            try:
                event, code = events.get(timeout=0.3)
            except queue.Empty:
                event, code = None, None
            if event == "playback_play":
                if code != 0:
                    raise stream.StreamError("player_play_failed", player_status=code)
                playing = True
                emit("player_running", player_reported_play=True)
            elif event in ("playback_open", "output_open") and code != 0:
                raise stream.StreamError(event + "_failed", player_status=code)
            elif args.vod and event and event.startswith("control_"):
                commands = {"control_pause": b"p\n", "control_resume": b"c\n",
                            "control_seek_back": b"kf-30\n", "control_seek_forward": b"kf30\n"}
                command = commands.get(event)
                if command and playing and player.poll() is None:
                    player.stdin.write(command)
                    player.stdin.flush()
            elif args.vod and event == "playback_stop" and code == 0 and playing:
                emit("vod_ended")
                return 0
            elif args.vod and event in ("playback_pause", "playback_continue", "playback_seek"):
                if code != 0:
                    emit("vod_control_failed")
                elif event == "playback_pause":
                    emit("vod_paused")
                elif event == "playback_continue":
                    emit("vod_resumed")
            elif event and code is None:
                raise stream.StreamError(event)
            if player.poll() is not None:
                if args.vod and playing and player.returncode == 0:
                    emit("vod_ended")
                    return 0
                raise stream.StreamError("player_exited", player_exit_code=player.returncode,
                                         player_reported_play=playing)
            if not playing and time.monotonic() - started > 60:
                raise stream.StreamError("player_start_timeout")
        emit("stopped")
        return 0
    except KeyboardInterrupt:
        emit("stopped")
        return 0
    except Exception as error:
        reason = error.reason if isinstance(error, (stream.StreamError, channels.ChannelError, drm.ProbeError)) else type(error).__name__
        details = getattr(error, "details", {})
        safe = {key: value for key, value in details.items()
                if key in ("http_status", "player_status", "player_exit_code", "player_reported_play")
                and isinstance(value, (int, bool))}
        if vod_api is not None:
            safe["vod_step"] = vod_api.stage
            diagnostic = getattr(vod_api, "diagnostic", {})
            if isinstance(diagnostic, dict) and diagnostic:
                safe["vod_http_diagnostic"] = diagnostic
        emit("error", reason=reason, **safe)
        return 1
    finally:
        stop_player(player)
        if server is not None:
            server.shutdown()
            server.server_close()
        keys.clear()


if __name__ == "__main__":
    raise SystemExit(main())
