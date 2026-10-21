#!/usr/bin/env python3
"""Standalone CANAL+ PL live-channel initialization, standard library only.

Consumes the session produced by canal_login_test.py. Request and response
structure follows CANAL+'s public web player (main.HaxvXngO.js, 2026-10-20).
This does not play video or extract DRM keys. Sensitive responses stay local.
"""

import argparse
import datetime
import json
import os
from pathlib import Path
import re
import ssl
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid

API_HOST = "ltv.slc-app-aka.prod.bo.canal.canalplustech.pro"
INIT_URL = ("https://" + API_HOST
            + "/api/V4/zones/cppol/devices/3/apps/1/jobs/InitLiveTV")
DEFAULT_SESSION_FILE = "/etc/canal-e2/session.json"
MAX_RESPONSE_BYTES = 12 * 1024 * 1024


class ChannelError(Exception):
    def __init__(self, reason, **details):
        super().__init__(reason)
        self.reason = reason
        self.details = details


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if (target.scheme != "https" or target.hostname != API_HOST
                or target.port not in (None, 443) or target.username or target.password):
            raise ChannelError("unexpected_redirect", http_status=code)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def atomic_private_json(path, value):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".canal-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_json(path):
    try:
        with Path(path).open(encoding="utf-8") as source:
            value = json.load(source)
    except FileNotFoundError:
        raise ChannelError("local_file_missing", file=str(path)) from None
    except (OSError, ValueError):
        raise ChannelError("local_file_unreadable", file=str(path)) from None
    if not isinstance(value, dict):
        raise ChannelError("invalid_local_file_format", file=str(path))
    return value


def get_client_ids(path):
    path = Path(path)
    if path.exists():
        ids = load_json(path)
        for key in ("UserKeyId", "DeviceKeyId"):
            value = ids.get(key)
            if not isinstance(value, str) or not 10 < len(value) < 128:
                raise ChannelError("invalid_saved_client_ids")
        return ids
    ids = {"UserKeyId": str(uuid.uuid4()), "DeviceKeyId": str(uuid.uuid4())}
    atomic_private_json(path, ids)
    return ids


def make_request(pass_token, ids):
    # These are local client identifiers, not DRM device credentials.
    return {"ServiceRequest": {"InData": {
        "UseRmuTokenPlaceHolder": True,
        "PassData": {"Id": 0, "Token": pass_token},
        "UserKeyId": ids["UserKeyId"],
        "DeviceKeyId": ids["DeviceKeyId"],
        "PDSData": {"GroupTypes": "1"},
        "DeviceSpecificities": {"BpkCompatibility": True},
    }}}


def fetch_init(payload, opener=None):
    opener = opener or urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        SameOriginRedirect(),
    )
    request = urllib.request.Request(
        INIT_URL, method="POST", data=json.dumps(payload).encode("utf-8"),
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux armv7l) CANAL-E2-Channels-Test/0.1",
            "Content-Type": "application/json;charset=utf-8",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pl-PL,pl;q=0.9",
            "Origin": "https://www.canalplus.com",
            "Referer": "https://www.canalplus.com/",
        },
    )
    try:
        response = opener.open(request, timeout=25)
    except urllib.error.HTTPError as error:
        response = error
    except urllib.error.URLError:
        raise ChannelError("connection_or_tls_error") from None
    with response:
        status = response.code
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ChannelError("response_too_large", http_status=status)
    if status != 200:
        raise ChannelError("http_error", http_status=status)
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ChannelError("service_returned_non_json", http_status=status) from None
    if not isinstance(value, dict):
        raise ChannelError("unexpected_response_type", http_status=status)
    return value


def numeric_service_status(value):
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        text = str(value)
        if re.fullmatch(r"[0-9.-]{1,15}", text):
            return text
    return None


def extract_outdata(response):
    service = response.get("ServiceResponse")
    if not isinstance(service, dict):
        raise ChannelError("missing_service_response")
    out = service.get("OutData")
    if not isinstance(out, dict) or not isinstance(out.get("PDS"), dict):
        code = numeric_service_status(service.get("Status"))
        details = {"service_status": code} if code is not None else {}
        raise ChannelError("live_initialization_failed", **details)
    return out


def as_list(value, wrapper=None):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        if wrapper is not None and wrapper in value:
            return as_list(value[wrapper])
        return [value]
    return []


def authorized(channel):
    rights = channel.get("AccessRights")
    value = rights.get("NoAccess") if isinstance(rights, dict) else None
    if value is False or (isinstance(value, str) and value.lower() == "false"):
        return True
    if value is True or (isinstance(value, str) and value.lower() == "true"):
        return False
    return None


def normalize_channels(out):
    groups = out.get("PDS", {}).get("ChannelsGroups", {})
    if not isinstance(groups, dict):
        raise ChannelError("unexpected_channel_groups")
    by_id = {}
    for group in as_list(groups.get("ChannelsGroup")):
        if not isinstance(group, dict):
            continue
        for channel in as_list(group.get("Channels"), "Channel"):
            if not isinstance(channel, dict):
                continue
            epg_id, name = channel.get("EpgId"), channel.get("Name")
            if epg_id is None or not isinstance(name, str) or not name.strip():
                continue
            if not re.fullmatch(r"[0-9]{1,12}", str(epg_id)):
                continue
            entry = {"epg_id": str(epg_id), "name": name,
                     "authorized": authorized(channel), "raw": channel}
            previous = by_id.get(entry["epg_id"])
            if previous is None or (entry["authorized"] is True
                                    and previous["authorized"] is not True):
                by_id[entry["epg_id"]] = entry
    return list(by_id.values())


def has_stream_reference(channel):
    if isinstance(channel.get("WSXUrl"), str) and channel["WSXUrl"]:
        return True
    assets = channel.get("AssetUrls")
    if not isinstance(assets, dict):
        return False
    ott = assets.get("OttUrls")
    return isinstance(ott, dict) and any(isinstance(v, str) and bool(v) for v in ott.values())


def summarize(channels, output_path):
    granted = [c for c in channels if c["authorized"] is True]
    preview = granted or channels
    return {
        "status": "CHANNELS_LOADED",
        "channel_count": len(channels),
        "authorized_count": len(granted),
        "unknown_access_count": sum(c["authorized"] is None for c in channels),
        "channels_with_stream_reference": sum(has_stream_reference(c["raw"]) for c in channels),
        "sample_channels": [c["name"] for c in preview[:12]],
        "live_file": str(output_path),
        "account_tokens_printed": False,
        "video_playback_tested": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Pobranie kanalow CANAL+ z lokalnej sesji")
    parser.add_argument("--session-file", default=DEFAULT_SESSION_FILE)
    args = parser.parse_args()
    stage = "read_session"
    try:
        session_path = Path(args.session_file).expanduser()
        session = load_json(session_path)
        auth = session.get("authentication")
        if not isinstance(auth, dict) or not auth.get("passToken") or not auth.get("passId"):
            raise ChannelError("authenticated_session_missing")
        pass_token = auth["passToken"]
        if not isinstance(pass_token, str):
            raise ChannelError("invalid_pass_token_type")
        stage = "prepare_client_ids"
        ids = get_client_ids(session_path.with_name("client.json"))
        stage = "init_live"
        response = fetch_init(make_request(pass_token, ids))
        stage = "parse_channels"
        out = extract_outdata(response)
        channels = normalize_channels(out)
        if not channels:
            raise ChannelError("no_channels_returned")
        stage = "save_live_data"
        live_path = session_path.with_name("live.json")
        atomic_private_json(live_path, {
            "schema_version": 1,
            "saved_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "session_saved_at_utc": session.get("saved_at_utc"),
            "client_ids": ids,
            "init_live_response": response,
            "channels": channels,
        })
        result = summarize(channels, live_path)
        exit_code = 0
    except ChannelError as error:
        result = {"status": "ERROR", "stage": stage,
                  "reason": error.reason, **error.details}
        exit_code = 1
    except Exception as error:
        result = {"status": "ERROR", "stage": stage, "reason": type(error).__name__}
        exit_code = 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
