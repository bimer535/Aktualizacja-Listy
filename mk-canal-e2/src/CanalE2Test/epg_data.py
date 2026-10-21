"""CANAL+ now/next metadata. No session, account or playback dependencies."""
import datetime
import html
import json
import math
import os
from pathlib import Path
import re
import ssl
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HOST = "secure-webtv-static.canal-plus.com"
URL = "https://" + HOST + "/metadata/cppol/all/v2.2/globalchannels.json"
CACHE = Path("/tmp/mk-canal-epg.json")
MAX_DOWNLOAD = 12 * 1024 * 1024
MAX_CACHE = 8 * 1024 * 1024
CACHE_SECONDS = 120


class EpgError(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def clean_text(value, maximum=1200):
    if not isinstance(value, str):
        return ""
    value = html.unescape(re.sub(r"<[^>]*>", " ", value))
    return " ".join(value.split())[:maximum]


def iso_timestamp(value):
    if not isinstance(value, str) or len(value) > 80:
        return None
    try:
        date = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if date.tzinfo is None:
            return None
        return int(date.timestamp())
    except (ValueError, OverflowError, OSError):
        return None


def normalize_events(events):
    if not isinstance(events, list):
        return []
    result = []
    for raw in events[:300]:
        if not isinstance(raw, dict):
            continue
        title = clean_text(raw.get("title"), 240)
        codes = raw.get("timecodes")
        if not title or not isinstance(codes, list) or not codes:
            continue
        blocks = []
        for code in codes[:20]:
            if not isinstance(code, dict):
                continue
            start = iso_timestamp(code.get("start"))
            duration = code.get("duration")
            if (start is not None and isinstance(duration, (int, float))
                    and not isinstance(duration, bool) and math.isfinite(duration)
                    and 0 < duration <= 7 * 86400 * 1000):
                blocks.append((start, start + int(duration / 1000)))
        if not blocks:
            continue
        start, end = min(b[0] for b in blocks), max(b[1] for b in blocks)
        if end <= start:
            continue
        subtitle = clean_text(raw.get("subTitle"), 400)
        description = next((clean_text(raw.get(key)) for key in
            ("description", "synopsis", "summary", "shortDescription", "longDescription")
            if clean_text(raw.get(key))), "")
        result.append({"title": title, "subtitle": subtitle, "description": description,
                       "start": start, "end": end})
    unique = {(p["start"], p["end"], p["title"]): p for p in result}
    return sorted(unique.values(), key=lambda p: (p["start"], p["end"]))


def choose_pair(programmes, now):
    current = next((p for p in reversed(programmes) if p["start"] <= now < p["end"]), None)
    following = next((p for p in programmes if p["start"] > now), None)
    return {"current": current, "next": following}


def normalize_feed(payload, now):
    channels = payload.get("channels") if isinstance(payload, dict) else None
    if not isinstance(channels, list) or not channels:
        raise EpgError("epg_invalid_response")
    entries = {}
    for channel in channels[:1500]:
        if not isinstance(channel, dict):
            continue
        channel_id = str(channel.get("id", ""))
        if not re.fullmatch(r"[0-9]{1,12}", channel_id):
            continue
        pair = choose_pair(normalize_events(channel.get("events")), now)
        # Keep only the two requested programmes, never a full programme guide.
        programmes = [p for p in (pair["current"], pair["next"]) if p is not None]
        boundaries = [p["end"] for p in programmes if p["start"] <= now < p["end"]]
        boundaries += [p["start"] for p in programmes if p["start"] > now]
        refresh_at = min([now + CACHE_SECONDS] + boundaries)
        entries[channel_id] = {"programmes": programmes, "refresh_at": refresh_at}
    if not entries:
        raise EpgError("epg_invalid_response")
    return {"schema": 1, "fetched_at": now, "channels": entries}


class SameOrigin(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if (target.scheme != "https" or target.hostname != HOST
                or target.port not in (None, 443) or target.username or target.password):
            raise EpgError("epg_unexpected_redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_feed():
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()), SameOrigin())
    request = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0",
        "Accept": "application/json", "Origin": "https://www.canalplus.com",
        "Referer": "https://www.canalplus.com/"})
    try:
        with opener.open(request, timeout=12) as response:
            body = response.read(MAX_DOWNLOAD + 1)
    except urllib.error.HTTPError as error:
        raise EpgError("epg_http_%d" % error.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise EpgError("epg_connection_error") from None
    if len(body) > MAX_DOWNLOAD:
        raise EpgError("epg_response_too_large")
    try:
        return json.loads(body)
    except (ValueError, UnicodeError):
        raise EpgError("epg_invalid_response") from None


def read_cache(path):
    try:
        if path.is_symlink() or path.stat().st_size > MAX_CACHE:
            return None
        data = json.loads(path.read_bytes())
        if (not isinstance(data, dict) or data.get("schema") != 1
                or not isinstance(data.get("fetched_at"), (int, float))
                or not isinstance(data.get("channels"), dict)):
            return None
        for channel in data["channels"].values():
            if not isinstance(channel, dict) or not isinstance(channel.get("refresh_at"), (int, float)):
                return None
            programmes = channel.get("programmes")
            if not isinstance(programmes, list) or len(programmes) > 2:
                return None
            for p in programmes:
                if (not isinstance(p, dict) or not isinstance(p.get("start"), int)
                        or not isinstance(p.get("end"), int) or p["end"] <= p["start"]
                        or any(not isinstance(p.get(k), str) for k in ("title", "subtitle", "description"))):
                    return None
        return data
    except (OSError, ValueError, TypeError):
        return None


def save_cache(path, data):
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_CACHE:
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".mk-canal-epg-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(body)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def get_pair(channel_id, path=CACHE, fetcher=fetch_feed, clock=time.time):
    channel_id = str(channel_id)
    if not re.fullmatch(r"[0-9]{1,12}", str(channel_id)):
        raise EpgError("epg_invalid_channel")
    now = clock()
    cache = read_cache(path)
    entry = cache["channels"].get(channel_id) if cache else None
    age = now - cache["fetched_at"] if cache else None
    if cache and 0 <= age < CACHE_SECONDS and (entry is None or now < entry["refresh_at"]):
        return dict(choose_pair(entry["programmes"] if entry else [], now), cached=False)
    try:
        cache_new = normalize_feed(fetcher(), clock())
    except EpgError:
        # A cached programme is still shown only within its real time window.
        if entry and 0 <= age < 900:
            pair = choose_pair(entry["programmes"], now)
            if pair["current"] or pair["next"]:
                return dict(pair, cached=True)
        raise
    try:
        save_cache(path, cache_new)
    except OSError:
        pass  # A full /tmp must not prevent displaying freshly fetched metadata.
    entry = cache_new["channels"].get(channel_id)
    return dict(choose_pair(entry["programmes"] if entry else [], clock()), cached=False)
