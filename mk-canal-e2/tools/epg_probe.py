#!/usr/bin/env python3
"""Read only: report CANAL+ now/next metadata structure without account access."""
import datetime
import html
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

HOST = "secure-webtv-static.canal-plus.com"
URL = "https://" + HOST + "/metadata/cppol/all/v2.2/globalchannels.json"
LIMIT = 12 * 1024 * 1024


class SameOrigin(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if (target.scheme != "https" or target.hostname != HOST
                or target.port not in (None, 443) or target.username or target.password):
            raise ValueError("unexpected_redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def text(value, maximum=300):
    if not isinstance(value, str):
        return None
    value = html.unescape(re.sub(r"<[^>]*>", " ", value))
    return " ".join(value.split())[:maximum]


def timestamp(event):
    try:
        stamp = event["timecodes"][0]["start"]
        date = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if date.tzinfo is None:
            return None
        return date.timestamp()
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        return None


def inspect(payload):
    channels = payload.get("channels")
    if not isinstance(channels, list):
        raise ValueError("missing_channels")
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    examples = []
    for channel in channels:
        if not isinstance(channel, dict) or not isinstance(channel.get("events"), list):
            continue
        events = sorted(((timestamp(e), e) for e in channel["events"]
                         if isinstance(e, dict) and timestamp(e) is not None), key=lambda pair: pair[0])
        if not events:
            continue
        current = next((i for i in range(len(events) - 1, -1, -1) if events[i][0] <= now), 0)
        selected = []
        for _, event in events[current:current + 2]:
            fields = {k: text(event[k]) for k in ("title", "subTitle", "genre", "description",
                      "shortDescription", "longDescription", "synopsis", "summary", "pitch") if text(event.get(k))}
            codes = event.get("timecodes", [])
            selected.append({"field_types": {k: type(v).__name__ for k, v in event.items()},
                             "text_fields": fields,
                             "timecodes": [{k: c[k] for k in ("start", "duration", "type") if k in c}
                                           for c in codes[:3] if isinstance(c, dict)]})
        examples.append({"epg_id": str(channel.get("id", ""))[:30],
                         "channel": text(channel.get("name")),
                         "channel_fields": list(channel)[:30], "sample_events": selected})
        if len(examples) == 2:
            break
    return {"status": "METADATA_OK", "channel_count": len(channels), "samples": examples,
            "account_files_read": False, "configuration_changed": False}


def main():
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()), SameOrigin())
    request = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0",
        "Accept": "application/json", "Origin": "https://www.canalplus.com",
        "Referer": "https://www.canalplus.com/"})
    try:
        with opener.open(request, timeout=25) as response:
            body = response.read(LIMIT + 1)
        if len(body) > LIMIT:
            raise ValueError("response_too_large")
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("unexpected_response_type")
        report = inspect(payload)
    except urllib.error.HTTPError as error:
        report = {"status": "HTTP_ERROR", "http_status": error.code}
    except urllib.error.URLError:
        report = {"status": "CONNECTION_OR_TLS_ERROR"}
    except Exception as error:
        report = {"status": "ERROR", "reason": type(error).__name__}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
