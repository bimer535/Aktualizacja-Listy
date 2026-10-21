#!/usr/bin/env python3
"""Experimental standalone CANAL+ stream/license test; does not play video.

Requires our canal_channels_test.py and canal_drm_demo.py in the same folder.
No E2iPlayer or ArchivCZSK application imports. No account/DRM keys are printed
or saved. The public DRM source is fetched and checked by canal_drm_demo.py.
"""

import argparse
import base64
import contextlib
import datetime
import gzip
import importlib
import io
import ipaddress
import json
import logging
import re
import ssl
import struct
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

WV_UUID = "edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"
# Host and route from the owner's static reference report. Widevine profile 31
# remains from the public integration reference; its literal was redacted in the report.
LICENSE_URL = ("https://ltv.slc-app-aka.prod.bo.canal.canalplustech.pro"
               "/api/V4/zones/cppol/devices/31/apps/1/jobs/GetLicence")
TEST_VERSION = 2
DIAGNOSTIC_REVISION = 4
MAX_BODY = 4 * 1024 * 1024


class StreamError(Exception):
    def __init__(self, reason, **details):
        super().__init__(reason)
        self.reason = reason
        self.details = details


def checked_url(url, base=None):
    if not isinstance(url, str) or not url or len(url) > 32768:
        raise StreamError("invalid_stream_url")
    if base:
        url = urllib.parse.urljoin(base, url)
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme not in ("http", "https") or not parts.hostname
            or parts.username or parts.password or "{" in url or "}" in url):
        raise StreamError("invalid_or_unresolved_stream_url")
    if parts.hostname.lower() in ("localhost", "localhost.localdomain"):
        raise StreamError("non_public_stream_url")
    try:
        address = ipaddress.ip_address(parts.hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise StreamError("non_public_stream_url")
    return url


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_url(newurl, req.full_url)
        old, new = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        if old.scheme == "https" and new.scheme != "https":
            raise StreamError("insecure_redirect", http_status=code)
        if req.data is not None and (old.scheme, old.hostname, old.port) != (
                new.scheme, new.hostname, new.port):
            raise StreamError("unexpected_license_redirect", http_status=code)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Http:
    def __init__(self, user_agent=None):
        self.user_agent = user_agent or "Mozilla/5.0 (X11; Linux armv7l) CANAL-E2-Stream-Test/0.1"
        self.last_response_metadata = {}
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl.create_default_context()), SafeRedirect())

    def read(self, url, payload=None):
        self.last_response_metadata = {}
        url = checked_url(url)
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "*/*", "Accept-Language": "pl-PL,pl;q=0.9",
            "Origin": "https://www.canalplus.com",
            "Referer": "https://www.canalplus.com/",
            "Accept-Encoding": "identity",
        }
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers,
                                         method="POST" if body is not None else "GET")
        try:
            response = self.opener.open(request, timeout=25)
        except urllib.error.HTTPError as error:
            response = error
        except urllib.error.URLError:
            raise StreamError("connection_or_tls_error") from None
        with response:
            status = response.code
            content = response.read(MAX_BODY + 1)
            final_url = response.url
            mime = response.headers.get_content_type().lower()
            encoding = response.headers.get("Content-Encoding", "identity").strip().lower()
        self.last_response_metadata = {
            "http_status": status,
            "response_content_type": mime if re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+", mime) else "unknown",
            "response_content_encoding": encoding if encoding in ("identity", "gzip", "deflate", "br") else "unknown",
            "response_bytes": len(content),
            "response_redirected": final_url != url,
        }
        if status != 200:
            raise StreamError("http_error", http_status=status)
        if len(content) > MAX_BODY:
            raise StreamError("response_too_large")
        if encoding == "gzip":
            try:
                with gzip.GzipFile(fileobj=io.BytesIO(content)) as compressed:
                    content = compressed.read(MAX_BODY + 1)
            except (OSError, EOFError):
                raise StreamError("invalid_gzip_response") from None
            if len(content) > MAX_BODY:
                raise StreamError("response_too_large")
        elif encoding != "identity":
            raise StreamError("unsupported_response_encoding", **self.last_response_metadata)
        return content, checked_url(final_url)


def select_channel(channels, requested):
    requested = requested.strip().casefold()
    matches = [c for c in channels if (c.get("name", "").strip().casefold() == requested
                                      or str(c.get("epg_id", "")) == requested)]
    if len(matches) != 1:
        raise StreamError("channel_not_found_or_ambiguous")
    if matches[0].get("authorized") is not True:
        raise StreamError("channel_not_authorized")
    return matches[0]


def entry_url(channel, out):
    raw = channel["raw"]
    value = raw.get("WSXUrl")
    if not isinstance(value, str) or not value:
        assets = raw.get("AssetUrls", {})
        ott = assets.get("OttUrls", {}) if isinstance(assets, dict) else {}
        value = ott.get("Default") if isinstance(ott, dict) else None
    if not isinstance(value, str) or not value:
        raise StreamError("missing_stream_reference")
    replacement = out.get("RMUToken")
    if replacement:
        encoded = urllib.parse.quote(str(replacement), safe="")
        value = value.replace("{RMUToken}", encoded)
        value = re.sub("%7bRMUToken%7d", lambda _: encoded, value, flags=re.IGNORECASE)
    return checked_url(value)


def descriptor_candidates(value, base):
    candidates = []

    def walk(node, path=()):
        if len(path) > 12:
            return
        if isinstance(node, dict):
            for key, child in node.items():
                if not isinstance(key, str) or any(word in key.lower()
                        for word in ("license", "licence", "certificate", "tracking", "image", "logo")):
                    continue
                walk(child, path + (key.lower(),))
        elif isinstance(node, list):
            for child in node[:100]:
                walk(child, path)
        elif isinstance(node, str) and path:
            if path[-1] not in ("src", "url", "manifest", "manifesturl", "mpd", "dash"):
                return
            try:
                url = checked_url(node, base)
            except StreamError:
                return
            score = (0 if ".mpd" in urllib.parse.urlsplit(url).path.lower() else 10)
            # The reference host uses descriptor.primary.src for live channels.
            score += 0 if "primary" in path else 1 if "dvr" in path else 2 if "live" in path else 4
            candidates.append((score, url))

    walk(value)
    return [url for _, url in sorted(candidates, key=lambda item: item[0])]


def resolve_mpd(http, start_url):
    url = start_url
    visited = set()
    descriptor_fields = set()
    for _ in range(6):
        if url in visited:
            raise StreamError("stream_reference_loop")
        visited.add(url)
        raw, final = http.read(url)
        stripped = raw.lstrip(b"\xef\xbb\xbf \r\n\t")
        if stripped.startswith(b"#EXTM3U"):
            raise StreamError("hls_received_instead_of_dash")
        if stripped.startswith((b"{", b"[")):
            try:
                descriptor = json.loads(raw)
            except (ValueError, UnicodeError):
                raise StreamError("invalid_stream_descriptor") from None
            if isinstance(descriptor, dict):
                descriptor_fields.update(k for k in descriptor if isinstance(k, str)
                    and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,50}", k))
            candidates = descriptor_candidates(descriptor, final)
            if not candidates:
                raise StreamError("descriptor_has_no_supported_url",
                                  descriptor_field_names=sorted(descriptor_fields))
            url = candidates[0]
            continue
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            raise StreamError("unrecognized_stream_response") from None
        kind = root.tag.rsplit("}", 1)[-1]
        if kind == "MPD":
            return root, final
        if kind.lower() == "smoothstreamingmedia":
            raise StreamError("smooth_streaming_received_instead_of_dash")
        sources = [node.attrib.get("src") for node in root.iter() if node.attrib.get("src")]
        sources.sort(key=lambda source: 0 if ".mpd" in source.lower() else 1)
        if not sources:
            raise StreamError("xml_descriptor_has_no_stream")
        url = checked_url(sources[0], final)
    raise StreamError("too_many_stream_reference_steps")


def manifest_info(root):
    pssh = []
    protections = []
    videos = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag == "ContentProtection":
            scheme = node.attrib.get("schemeIdUri", "").lower()
            if WV_UUID in scheme:
                protections.append("widevine")
                for child in node.iter():
                    if child.tag.rsplit("}", 1)[-1] == "pssh" and child.text:
                        value = "".join(child.text.split())
                        try:
                            decoded = base64.b64decode(value, validate=True)
                        except ValueError:
                            continue
                        if 32 <= len(decoded) <= 65536 and value not in pssh:
                            pssh.append(value)
            elif "9a04f079-9840-4286-ab92-e65be0885f95" in scheme:
                protections.append("playready")
            elif "mp4protection" in scheme:
                protections.append("common_encryption")
        if tag == "Representation" and node.attrib.get("height", "").isdigit():
            videos.append(int(node.attrib["height"]))
    return {"drm_systems": sorted(set(protections)),
            "widevine_pssh_count": len(pssh),
            "video_heights": sorted(set(videos))}, pssh


def select_video_pssh(root, maximum_height):
    """Follow DASH protection inheritance for the selected video rendition."""
    def tag(node):
        return node.tag.rsplit("}", 1)[-1]

    def own_pssh(node):
        result = []
        for child in node:
            if tag(child) != "ContentProtection":
                continue
            if WV_UUID not in child.attrib.get("schemeIdUri", "").lower():
                continue
            for item in child.iter():
                if tag(item) == "pssh" and item.text:
                    value = "".join(item.text.split())
                    if value not in result:
                        result.append(value)
        return result

    def positive_int(value):
        try:
            number = int(value)
            return number if number > 0 else 0
        except (ValueError, TypeError):
            return 0

    tracks = []
    root_pssh = own_pssh(root)
    periods = [node for node in root if tag(node) == "Period"]
    for period_index, period in enumerate(periods):
        period_pssh = own_pssh(period) or root_pssh
        for adaptation in period:
            if tag(adaptation) != "AdaptationSet":
                continue
            adaptation_pssh = own_pssh(adaptation) or period_pssh
            for representation in adaptation:
                if tag(representation) != "Representation":
                    continue
                attributes = {**adaptation.attrib, **representation.attrib}
                height = positive_int(attributes.get("height"))
                mime = attributes.get("mimeType", "").lower()
                content_type = attributes.get("contentType", "").lower()
                if content_type != "video" and not mime.startswith("video/") and not height:
                    continue
                tracks.append({
                    "height": height,
                    "bandwidth": positive_int(attributes.get("bandwidth")),
                    "codecs": attributes.get("codecs", ""),
                    "pssh": own_pssh(representation) or adaptation_pssh,
                    "period_index": period_index,
                })
        # Do not combine keys from different periods or ad breaks.
        if tracks:
            break
    if not tracks or not any(track["height"] for track in tracks):
        raise StreamError("video_resolution_unavailable")
    choices = [track for track in tracks if 0 < track["height"] <= maximum_height]
    if not choices:
        raise StreamError("requested_resolution_unavailable",
                          available_video_heights=sorted({track["height"] for track in tracks}))
    selected = max(choices, key=lambda track: (
        track["height"], track["codecs"].lower().startswith("avc"), track["bandwidth"]))
    safe_codec = selected["codecs"]
    if not re.fullmatch(r"[A-Za-z0-9_., -]{0,80}", safe_codec):
        safe_codec = "[codec omitted]"
    metadata = {
        "requested_max_height": maximum_height,
        "selected_video_height": selected["height"],
        "selected_video_codec": safe_codec,
        "selected_video_pssh_count": len(selected["pssh"]),
        "selected_period_index": selected["period_index"],
    }
    return metadata, selected["pssh"]


def normalize_pssh(value):
    """Normalize a Widevine PSSH v1 box for the public engine's v0 parser."""
    try:
        raw = base64.b64decode(value, validate=True)
    except ValueError:
        raise StreamError("invalid_widevine_pssh") from None
    if len(raw) < 32 or raw[4:8] != b"pssh" or raw[12:28].hex() != WV_UUID.replace("-", ""):
        raise StreamError("invalid_widevine_pssh")
    size = struct.unpack(">I", raw[:4])[0]
    if size != len(raw):
        raise StreamError("invalid_widevine_pssh_size")
    version = raw[8]
    if version == 0:
        if struct.unpack(">I", raw[28:32])[0] != len(raw) - 32:
            raise StreamError("invalid_widevine_pssh_size")
        return value
    if version != 1 or len(raw) < 36:
        raise StreamError("unsupported_widevine_pssh_version")
    count = struct.unpack(">I", raw[28:32])[0]
    offset = 32 + count * 16
    if count > 1024 or offset + 4 > len(raw):
        raise StreamError("invalid_widevine_pssh_size")
    length = struct.unpack(">I", raw[offset:offset + 4])[0]
    data = raw[offset + 4:]
    if length != len(data):
        raise StreamError("invalid_widevine_pssh_size")
    if not data:
        # In WidevineCencHeader, repeated key_id is protobuf field 2.
        data = b"".join(b"\x12\x10" + raw[32 + i * 16:48 + i * 16]
                        for i in range(count))
    box = struct.pack(">I", 32 + len(data)) + b"pssh\0\0\0\0" + raw[12:28]
    return base64.b64encode(box + struct.pack(">I", len(data)) + data).decode("ascii")


def license_payload(channel, out, ids, challenge):
    token = out.get("LiveToken")
    if not isinstance(token, str) or not token:
        raise StreamError("missing_live_token")
    return {"ServiceRequest": {"InData": {
        "EpgId": int(channel["epg_id"]), "Mode": "MKPL", "LiveToken": token,
        "UserKeyId": ids["UserKeyId"], "DeviceKeyId": ids["DeviceKeyId"],
        "ChallengeInfo": base64.b64encode(challenge).decode("ascii"),
        # Request nonpersistent streaming; the report redacts the original value.
        "PersistentLicense": "false",
    }}}


def redacted_service_message(value, sensitive_values=()):
    if not isinstance(value, str):
        return None
    text = value
    # Remove known request/session values before any output truncation.
    for secret in sorted((str(v) for v in sensitive_values if v is not None and str(v)),
                         key=len, reverse=True):
        text = text.replace(secret, "[redacted]")
    text = re.sub(r"https?://[^\s<>\"']+", "[URL redacted]", text)
    text = re.sub(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[email redacted]", text)
    text = re.sub(r"(?i)bearer\s+[^\s,;]+", "Bearer [redacted]", text)
    text = re.sub(r"(?i)(?:token|password|passwd|secret|authorization|client_id|clientid|userid|accountid|passid|deviceid)\s*[:=]\s*[^\s,;]+", "[credential redacted]", text)
    text = re.sub(r"[A-Za-z0-9_+/=-]{20,}", "[value redacted]", text)
    text = re.sub(r"\b[0-9]{6,}\b", "[number redacted]", text)
    text = " ".join(text.split())
    return text[:320] if text else None


def service_error_details(service, sensitive_values=()):
    details = {}
    code = service.get("Status")
    if re.fullmatch(r"[0-9.-]{1,15}", str(code)):
        details["service_status"] = str(code)
    names = []
    messages = {}
    message_fields = {"message", "statusmessage", "statusmsg", "errormessage", "errordescription",
                      "description", "faultstring", "reason", "error", "statusinfo"}
    def walk(value, path=(), depth=0):
        if not isinstance(value, dict) or depth > 2:
            return
        for key, item in value.items():
            if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,47}", key):
                continue
            if re.fullmatch(r"[a-fA-F0-9]{16,}", key):
                continue
            label = ".".join(path + (key,))
            names.append(label)
            if key.lower() in message_fields and isinstance(item, str):
                safe = redacted_service_message(item, sensitive_values)
                if safe:
                    messages[label] = safe
            if isinstance(item, dict) and (depth == 0 or key.lower() in ("error", "fault")):
                walk(item, path + (key,), depth + 1)
    walk(service)
    details["response_field_names_only"] = sorted(set(names))[:40]
    if messages:
        details["service_messages_redacted"] = dict(list(messages.items())[:5])
    return details


def license_response_shape(raw, sensitive_values=()):
    """Report bounded response structure; never include raw bodies or arbitrary keys."""
    details = {"response_bytes_decoded": len(raw)}
    stripped = raw.lstrip(b"\xef\xbb\xbf \r\n\t")
    if not stripped:
        return {**details, "response_format": "empty"}
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        prefix = stripped[:1024].lower()
        kind = "html" if b"<!doctype html" in prefix or b"<html" in prefix else (
            "xml" if prefix.startswith((b"<?xml", b"<")) else "other")
        return {**details, "response_format": kind}
    details["response_format"] = "json"
    details["json_root_type"] = type(data).__name__
    allowed = {"ServiceResponse", "OutData", "LicenseInfo", "Status", "Message",
               "Error", "Errors", "ErrorCode", "ErrorMessage", "StatusMessage", "StatusMsg",
               "error", "errors", "errorCode", "errorMessage", "error_description",
               "message", "status", "code", "detail", "title", "type", "data",
               "response", "result", "fault", "Fault", "faultcode", "faultstring"}
    if isinstance(data, dict):
        details["json_top_known_fields"] = sorted(key for key in data if key in allowed)
        details["json_top_other_field_count"] = sum(key not in allowed for key in data)
        messages = {}
        codes = {}
        def walk(node, path=(), depth=0):
            if not isinstance(node, dict) or depth > 2:
                return
            for key, value in node.items():
                if key not in allowed:
                    continue
                label = ".".join(path + (key,))
                if key.lower() in ("status", "code", "errorcode", "faultcode"):
                    if isinstance(value, (str, int)) and re.fullmatch(r"-?[0-9]{1,9}", str(value)):
                        codes[label] = str(value)
                if key.lower() in ("message", "errormessage", "statusmessage", "statusmsg", "error_description", "faultstring", "detail", "title", "error"):
                    safe = redacted_service_message(value, sensitive_values)
                    if safe:
                        messages[label] = safe
                if isinstance(value, dict):
                    walk(value, path + (key,), depth + 1)
        walk(data)
        if messages:
            details["response_messages_redacted"] = dict(list(messages.items())[:5])
        if codes:
            details["response_numeric_codes"] = dict(list(codes.items())[:10])
    return details


def read_license_response(raw, sensitive_values=()):
    try:
        data = json.loads(raw)
    except (ValueError, TypeError, UnicodeError):
        raise StreamError("invalid_license_response", **license_response_shape(raw, sensitive_values)) from None
    if (isinstance(data, dict) and "ServiceResponse" not in data
            and isinstance(data.get("Status"), (str, int))
            and re.fullmatch(r"-?[0-9]{1,9}", str(data["Status"]))
            and int(data["Status"]) != 0):
        raise StreamError("license_service_error", **license_response_shape(raw, sensitive_values))
    service = data.get("ServiceResponse") if isinstance(data, dict) else None
    if not isinstance(service, dict):
        raise StreamError("invalid_license_response", **license_response_shape(raw, sensitive_values))
    out = service.get("OutData")
    value = out.get("LicenseInfo") if isinstance(out, dict) else None
    if not isinstance(value, str) or not value:
        raise StreamError("license_not_granted", **service_error_details(service, sensitive_values))
    try:
        license_data = base64.b64decode("".join(value.split()), validate=True)
    except ValueError:
        raise StreamError("invalid_license_encoding") from None
    if not license_data:
        raise StreamError("empty_license_response")
    return license_data


def check_license(engine_dir, engine_helper, http, pssh, channel, out, ids, key_callback=None,
                  license_request=None):
    for relative, digest in engine_helper.SOURCE_HASHES.items():
        import hashlib
        path = engine_dir / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise StreamError("drm_source_checksum_mismatch")
    engine_helper.check_crypto()
    sys.path.insert(0, str(engine_dir))
    logging.disable(logging.CRITICAL)
    from tools_cenc.wvl3.cdm.cdm import Cdm
    from tools_cenc.wvl3.cdm.deviceconfig import DeviceConfig
    cdm = Cdm(logging.getLogger("disabled"))
    session_id = None
    try:
        session_id = cdm.open_session(normalize_pssh(pssh), DeviceConfig())
        if not isinstance(session_id, bytes):
            raise StreamError("drm_session_creation_failed")
        # Reference E2iDRMProv.getServiceCertificate returns None.
        # Let the CDM create its normal request without an extra certificate.
        challenge = cdm.get_license_request(session_id)
        if not isinstance(challenge, bytes):
            raise StreamError("license_challenge_creation_failed")
        if license_request is not None:
            license_data = license_request(challenge)
        else:
            try:
                raw, _ = http.read(LICENSE_URL, license_payload(channel, out, ids, challenge))
            except StreamError as error:
                error.details.update(http.last_response_metadata)
                error.details["license_step"] = "get_licence"
                raise
            request_secrets = (out.get("LiveToken"), out.get("RMUToken"),
                               ids.get("UserKeyId"), ids.get("DeviceKeyId"),
                               base64.b64encode(challenge).decode("ascii"))
            try:
                license_data = read_license_response(raw, request_secrets)
            except StreamError as error:
                error.details.update(http.last_response_metadata)
                error.details["license_step"] = "get_licence"
                raise
        if cdm.provide_license(session_id, license_data) != 0:
            raise StreamError("license_processing_failed")
        keys = [key for key in cdm.get_keys(session_id) if key.type == "CONTENT"]
        count = len(keys)
        if key_callback is not None:
            key_callback(keys)
        if count == 0:
            raise StreamError("license_has_no_content_keys")
        return count
    finally:
        if session_id is not None:
            cdm.close_session(session_id)


def main():
    parser = argparse.ArgumentParser(description="Test strumienia i licencji jednego kanalu CANAL+ (wersja 2)")
    parser.add_argument("--channel", default="CANAL+ 360 HD")
    parser.add_argument("--height", type=int, default=1080,
                        help="maksymalna wysokosc obrazu, domyslnie 1080")
    parser.add_argument("--session-file", default="/etc/canal-e2/session.json")
    parser.add_argument("--engine-dir", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.height <= 4320:
        parser.error("--height musi byc liczba od 1 do 4320")
    stage = "load_own_helpers"
    manifest = {}
    result = None
    try:
        try:
            channels_helper = importlib.import_module("canal_channels_test")
            engine_helper = importlib.import_module("canal_drm_demo")
        except ImportError:
            raise StreamError("missing_own_helper_files",
                              required_files=["canal_channels_test.py", "canal_drm_demo.py"]) from None
        stage = "refresh_live"
        session_path = Path(args.session_file)
        saved = channels_helper.load_json(session_path)
        auth = saved.get("authentication", {})
        if not isinstance(auth, dict) or not isinstance(auth.get("passToken"), str):
            raise StreamError("authenticated_session_missing")
        ids = channels_helper.get_client_ids(session_path.with_name("client.json"))
        response = channels_helper.fetch_init(channels_helper.make_request(auth["passToken"], ids))
        out = channels_helper.extract_outdata(response)
        channels = channels_helper.normalize_channels(out)
        selected = select_channel(channels, args.channel)
        channels_helper.atomic_private_json(session_path.with_name("live.json"), {
            "schema_version": 1, "saved_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "session_saved_at_utc": saved.get("saved_at_utc"), "client_ids": ids,
            "init_live_response": response, "channels": channels})
        stage = "resolve_stream"
        http = Http()
        root, _ = resolve_mpd(http, entry_url(selected, out))
        manifest, pssh = manifest_info(root)
        video_metadata, video_pssh = select_video_pssh(root, args.height)
        manifest.update(video_metadata)
        result = {"status": "STREAM_READY", "test_version": TEST_VERSION, "diagnostic_revision": DIAGNOSTIC_REVISION,
                  "channel": selected["name"], **manifest,
                  "account_tokens_printed": False, "drm_keys_printed": False,
                  "drm_keys_saved": False, "video_playback_tested": False}
        if manifest["drm_systems"]:
            if not video_pssh:
                raise StreamError("selected_video_has_no_widevine_pssh")
            stage = "prepare_public_drm_engine"
            # Upstream code can log session information: suppress its output.
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                if args.engine_dir:
                    stage = "canalplus_license"
                    count = check_license(args.engine_dir, engine_helper, http, video_pssh[0], selected, out, ids)
                else:
                    with tempfile.TemporaryDirectory(prefix="canal-drm-test-") as tmp:
                        directory = Path(tmp)
                        engine_helper.prepare_engine(directory)
                        stage = "canalplus_license"
                        count = check_license(directory, engine_helper, http, video_pssh[0], selected, out, ids)
            result.update(status="LICENSE_OK", content_key_count=count)
        exit_code = 0
    except KeyboardInterrupt:
        result = {"status": "CANCELLED", "stage": stage}
        exit_code = 130
    except Exception as error:
        details = getattr(error, "details", {})
        result = {"status": "ERROR", "test_version": TEST_VERSION, "diagnostic_revision": DIAGNOSTIC_REVISION, "stage": stage, **manifest,
                  "reason": getattr(error, "reason", type(error).__name__), **details,
                  "account_tokens_printed": False, "drm_keys_printed": False,
                  "video_playback_tested": False}
        if isinstance(error, urllib.error.HTTPError):
            result["http_status"] = error.code
        exit_code = 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
