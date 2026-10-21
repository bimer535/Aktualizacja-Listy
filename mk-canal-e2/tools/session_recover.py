#!/usr/bin/env python3
"""Renew an existing paired identity; save only after live-channel validation.

Uses the public CANAL+ PASS createToken protocol and the installed TV client.
No pairing credentials are imported from other applications. Account responses,
identity values, tokens and stream addresses are never printed.
"""
import argparse
import datetime
import json
from pathlib import Path
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

PLUGIN = Path('/usr/lib/enigma2/python/Plugins/Extensions/CanalE2Test')
TOKEN_URL = 'https://pass-api-v2.canal-plus.com/provider/services/pl/public/createToken'
TOKEN_HOST = 'pass-api-v2.canal-plus.com'
# Public portal identifier from the official CANAL+ PL web configuration.
PORTAL_ID = 'vbdTj7eb6aM.'
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
              'AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/153.0.0.0 Safari/537.36')
MAX_RESPONSE = 2 * 1024 * 1024


class RecoveryError(Exception):
    def __init__(self, reason, **details):
        super().__init__(reason)
        self.reason, self.details = reason, details


class SameTokenOrigin(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if (target.scheme != 'https' or target.hostname != TOKEN_HOST
                or target.port not in (None, 443) or target.username or target.password):
            raise RecoveryError('unexpected_token_redirect', http_status=code)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def renew(saved, opener=None):
    auth = saved.get('authentication', {})
    identity = auth.get('passId') if isinstance(auth, dict) else None
    device = saved.get('device_id')
    if (not isinstance(identity, str) or not identity or len(identity) > 8192
            or not isinstance(device, str) or not re.fullmatch(r'[a-zA-Z0-9-]{8,80}', device)):
        raise RecoveryError('paired_identity_missing')
    fields = {'passId': identity, 'deviceId': device, 'portailId': PORTAL_ID,
              'media': 'web', 'vect': 'Internet', 'zone': 'cppol',
              'passIdType': 'okta' if re.match(r'^\d{4}', identity) and identity[2:3] != '=' else 'pass',
              'noCache': 'false'}
    request = urllib.request.Request(TOKEN_URL, method='POST',
        data=urllib.parse.urlencode(fields).encode('utf-8'), headers={
            'User-Agent': USER_AGENT, 'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept-Language': 'pl-PL,pl;q=0.9',
            'Origin': 'https://www.canalplus.com', 'Referer': 'https://www.canalplus.com/pl/'})
    opener = opener or urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()), SameTokenOrigin())
    try:
        with opener.open(request, timeout=25) as response:
            status = response.code
            raw = response.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
        raise RecoveryError('token_refresh_http_error', http_status=status) from None
    except (urllib.error.URLError, OSError):
        raise RecoveryError('token_refresh_connection_error') from None
    if status != 200:
        raise RecoveryError('token_refresh_http_error', http_status=status)
    if len(raw) > MAX_RESPONSE:
        raise RecoveryError('token_refresh_response_too_large')
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        raise RecoveryError('token_refresh_non_json') from None
    result = data.get('response') if isinstance(data, dict) else None
    if not isinstance(result, dict):
        raise RecoveryError('token_refresh_invalid_response')
    code = result.get('errorCode')
    if str(code) != '0':
        details = {'service_error_code': str(code)} if re.fullmatch(r'-?\d{1,8}', str(code)) else {}
        raise RecoveryError('token_refresh_rejected', **details)
    if not all(isinstance(result.get(k), str) and result[k] for k in ('passId', 'passToken')):
        raise RecoveryError('token_refresh_missing_identity')
    user = result.get('userData')
    if isinstance(user, dict) and user.get('isAuthenticated') is False:
        raise RecoveryError('token_refresh_not_authenticated')
    return result


def recover(session_path, channels, opener=None):
    saved = channels.load_json(session_path)
    renewed = renew(saved, opener)
    ids = channels.load_json(session_path.with_name('client.json'))
    # Validate the new token using the SAME live API and saved client IDs.
    response = channels.fetch_init(channels.make_request(renewed['passToken'], ids))
    out = channels.extract_outdata(response)
    entries = channels.normalize_channels(out)
    count = sum(item.get('authorized') is True for item in entries)
    if count == 0:
        raise RecoveryError('renewed_identity_has_no_authorized_channels')
    updated = dict(saved)
    updated['authentication'] = {**saved['authentication'], **renewed}
    updated['saved_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # All remote checks passed. Keep account files private and use atomic writes.
    channels.atomic_private_json(session_path, updated)
    channels.atomic_private_json(session_path.with_name('live.json'), {
        'schema_version': 1, 'session_saved_at_utc': updated['saved_at_utc'],
        'client_ids': ids, 'init_live_response': response, 'channels': entries})
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--session-file', type=Path, default=Path('/etc/canal-e2/session.json'))
    args = parser.parse_args()
    if not (PLUGIN / 'canal_channels_test.py').is_file():
        print(json.dumps({'status': 'ERROR', 'reason': 'installed_tv_plugin_missing'}))
        return 2
    sys.path.insert(0, str(PLUGIN))
    import canal_channels_test as channels
    try:
        count = recover(args.session_file, channels)
        result = {'status': 'SESSION_RENEWED', 'authorized_channels': count,
                  'account_tokens_printed': False, 'video_playback_tested': False}
    except Exception as error:
        reason = getattr(error, 'reason', type(error).__name__)
        details = getattr(error, 'details', {})
        safe = {k: v for k, v in details.items()
                if k in ('http_status', 'service_status', 'service_error_code')
                and re.fullmatch(r'-?\d{1,8}', str(v))}
        result = {'status': 'ERROR', 'reason': reason, **safe, 'account_tokens_printed': False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'SESSION_RENEWED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
