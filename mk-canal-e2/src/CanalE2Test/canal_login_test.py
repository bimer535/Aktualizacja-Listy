#!/usr/bin/env python3
"""Standalone CANAL+ Poland device-code login test, standard library only.

Protocol derived from the owner's static authentication report auth-2.
No E2iPlayer imports. This program does not play video or request DRM keys.
Successful authentication is stored locally with permissions 0600.
"""

import argparse
import datetime
import http.cookiejar
import json
import os
from pathlib import Path
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

API_ROOT = "https://account.canalplus.com/"
GENERATE_URL = API_ROOT + "api/pass/generateAuthenticationToken"
LOGIN_URL = API_ROOT + "api/pass/loginByAuthenticationToken"
PAIRING_PAGE = "https://connect.canalplus.com/"
DEFAULT_SESSION_FILE = "/etc/canal-e2/session.json"
MAX_RESPONSE_BYTES = 1024 * 1024


class LoginError(Exception):
    def __init__(self, reason, *, status=None, error_code=None, fields=None):
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.error_code = error_code
        self.fields = fields


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if (target.scheme != "https" or target.hostname != "account.canalplus.com"
                or target.port not in (None, 443) or target.username or target.password):
            raise LoginError("unexpected_redirect", status=code)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def numeric_error(value):
    # Report service error numbers only; never echo arbitrary response strings.
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.isdecimal() and len(value) < 8:
        return int(value)
    return None


def response_field_names(data):
    return sorted(key for key in data if isinstance(key, str)
                  and len(key) < 80 and key.replace("_", "").isalnum())[:30]


class CanalLogin:
    def __init__(self, opener=None):
        self.opener = opener or urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
            SameOriginRedirect(),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        )

    def post(self, url, fields):
        request = urllib.request.Request(
            url, data=urllib.parse.urlencode(fields).encode("utf-8"), method="POST",
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux armv7l) CANAL-E2-Login-Test/0.1",
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": API_ROOT.rstrip("/"),
                "Referer": API_ROOT,
                "Accept-Language": "pl-PL,pl;q=0.9",
                "Cookie": "language=pl",
            },
        )
        try:
            response = self.opener.open(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        except urllib.error.URLError:
            raise LoginError("connection_or_tls_error") from None
        with response:
            status = response.code
            content = response.read(MAX_RESPONSE_BYTES + 1)
        if len(content) > MAX_RESPONSE_BYTES:
            raise LoginError("response_too_large", status=status)
        try:
            data = json.loads(content)
        except (ValueError, UnicodeError):
            raise LoginError("service_returned_non_json", status=status) from None
        if not isinstance(data, dict):
            raise LoginError("unexpected_response_type", status=status)
        if status not in (200, 400):
            raise LoginError("http_error", status=status,
                             error_code=numeric_error(data.get("errorCode")))
        return status, data

    def create_code(self, device_id):
        status, data = self.post(GENERATE_URL, {"deviceId": device_id})
        token = data.get("authenticationToken")
        if (status != 200 or not isinstance(token, (str, int))
                or isinstance(token, bool) or not str(token).strip()):
            raise LoginError("activation_code_not_received", status=status,
                             error_code=numeric_error(data.get("errorCode")),
                             fields=response_field_names(data))
        token = str(token)
        if len(token) > 128 or not all(c.isalnum() or c in "-_ " for c in token):
            raise LoginError("unexpected_activation_code_format", status=status)
        try:
            expires = int(data.get("expires_in", 300))
        except (ValueError, TypeError):
            expires = 300
        return token, min(900, max(1, expires))

    def check_code(self, device_id, token):
        status, data = self.post(LOGIN_URL, {
            "deviceId": device_id, "authenticationToken": token,
        })
        error_code = numeric_error(data.get("errorCode"))
        if error_code == 56:
            return None
        if error_code not in (None, 0):
            raise LoginError("service_rejected_login", status=status, error_code=error_code)
        if status == 200 and data.get("passId") and data.get("passToken"):
            return data
        raise LoginError("unexpected_login_response", status=status,
                         error_code=error_code, fields=response_field_names(data))


def save_session(path, device_id, authentication):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    payload = {
        "schema_version": 1,
        "device_id": device_id,
        "saved_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "authentication": authentication,
    }
    fd, temporary = tempfile.mkstemp(prefix=".session-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def emit_status(status, **fields):
    print(json.dumps({"status": status, **fields}, ensure_ascii=False, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description="Samodzielny test logowania CANAL+ kodem")
    parser.add_argument("--session-file", default=DEFAULT_SESSION_FILE)
    parser.add_argument("--probe", action="store_true",
                        help="sprawdz pobranie kodu bez pokazywania go i bez logowania")
    parser.add_argument("--new-login", action="store_true",
                        help="wykonaj nowe parowanie mimo istnienia zapisanej sesji")
    args = parser.parse_args()
    if Path(args.session_file).expanduser().exists() and not (args.new_login or args.probe):
        emit_status("SESSION_EXISTS", session_file=str(args.session_file),
                    message="Sesja juz istnieje. --new-login uruchamia nowe parowanie.",
                    session_validity_tested=False)
        return 0
    stage = "generate_code"
    try:
        device_id = str(uuid.uuid4())
        client = CanalLogin()
        token, expires = client.create_code(device_id)
        if args.probe:
            emit_status("CODE_GENERATION_OK", expires_in=expires,
                        authenticated=False, account_tokens_printed=False)
            return 0
        print("\nOtworz na telefonie lub komputerze: " + PAIRING_PAGE, flush=True)
        print("Zatwierdz na swoim koncie CANAL+ kod: " + token, flush=True)
        print("Czekam na zatwierdzenie. Ctrl+C przerywa probe.\n", flush=True)
        stage = "wait_for_approval"
        deadline = time.monotonic() + expires
        next_notice = time.monotonic() + 15
        while time.monotonic() < deadline:
            authentication = client.check_code(device_id, token)
            if authentication is not None:
                stage = "save_session"
                saved = save_session(args.session_file, device_id, authentication)
                emit_status("AUTHENTICATED", session_file=str(saved),
                            account_tokens_printed=False, video_playback_tested=False)
                return 0
            if time.monotonic() >= next_notice:
                print("Nadal czekam na zatwierdzenie...", flush=True)
                next_notice = time.monotonic() + 15
            time.sleep(min(3, max(0, deadline - time.monotonic())))
        raise LoginError("activation_code_expired")
    except KeyboardInterrupt:
        emit_status("CANCELLED", stage=stage)
        return 130
    except LoginError as error:
        detail = {"stage": stage, "reason": error.reason}
        if error.status is not None:
            detail["http_status"] = error.status
        if error.error_code is not None:
            detail["service_error_code"] = error.error_code
        if error.fields:
            detail["response_field_names_only"] = error.fields
        emit_status("ERROR", **detail)
        return 1
    except Exception as error:
        emit_status("ERROR", stage=stage, reason=type(error).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
