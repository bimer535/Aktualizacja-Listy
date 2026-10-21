#!/usr/bin/env python3
"""Compare two User-Agent values on authenticated, read-only VOD playset GETs.

No conso/view, licence, playback, purchase, pairing or account changes.
Credentials, arbitrary service messages and response bodies are never printed.
"""
import argparse
import json
from pathlib import Path
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

PLUGIN = Path('/usr/lib/enigma2/python/Plugins/Extensions/CanalE2Test')
sys.path.insert(0, str(PLUGIN))
REPORT = Path('/tmp/mk_canal_vod_probe.json')
BROWSER_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
              'AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/153.0.0.0 Safari/537.36')
ERROR_FIELDS = {'error', 'errors', 'errorCode', 'error_code', 'code', 'status', 'Status',
                'message', 'description', 'detail', 'error_description'}
CONTENT_FIELDS = {'comMode', 'contentId', 'distMode', 'distTechnology', 'drmType',
                  'functionalType', 'hash', 'idKey', 'quality'}


def error_shape(raw):
    result = {'response_bytes_read': len(raw)}
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        result['response_format'] = 'non_json'
        return result
    result['response_format'] = 'json'
    result['known_error_fields'] = []
    hints, codes = set(), {}
    def walk(node, depth=0):
        if depth > 3:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if key not in ERROR_FIELDS:
                    continue
                result['known_error_fields'].append(key)
                if key in ('errorCode', 'error_code', 'code', 'status', 'Status'):
                    if isinstance(value, int) and not isinstance(value, bool):
                        codes[key] = value
                    elif isinstance(value, str) and re.fullmatch(r'-?\d{1,8}', value):
                        codes[key] = int(value)
                if isinstance(value, str) and key in ('message', 'description', 'detail', 'error_description'):
                    text = value[:4000].casefold()
                    for tag, terms in [('user_agent_mentioned', ('user-agent', 'user agent', 'useragent')),
                                       ('token_mentioned', ('token', 'oauth')),
                                       ('device_mentioned', ('device', 'equipment')),
                                       ('expired_mentioned', ('expired', 'expiration')),
                                       ('subscription_mentioned', ('subscription', 'entitlement'))]:
                        if any(t in text for t in terms): hints.add(tag)
                walk(value, depth + 1)
        elif isinstance(node, list):
            for value in node[:10]: walk(value, depth + 1)
    walk(data)
    result['known_error_fields'] = sorted(set(result['known_error_fields']))
    if codes: result['service_codes'] = codes
    if hints: result['message_hint_tags'] = sorted(hints)
    return result


class ReadOnlyCapture:
    def __init__(self, opener):
        self.opener, self.summary = opener, {}

    def open(self, request, **kwargs):
        path = urllib.parse.urlsplit(request.full_url).path
        if request.get_method() != 'GET' or not path.startswith('/conso/playset/unit/'):
            raise ValueError('probe_read_only_guard')
        try:
            return self.opener.open(request, **kwargs)
        except urllib.error.HTTPError as error:
            try:
                raw = error.read(65536)
                self.summary = error_shape(raw)
            finally:
                error.close()
            raise


def probe_one(api_class, redirect_class, authentication, device_id, cid, name, agent=None):
    result = {'test': name}
    capture = ReadOnlyCapture(urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()), redirect_class()))
    try:
        client = api_class(authentication, device_id, opener=capture)
        if agent is not None:
            client.headers['User-Agent'] = agent
        data = client.playset(cid)
        available = data.get('available')
        result.update(status='PLAYSET_RECEIVED', http_status=200,
                      available_count=len(available) if isinstance(available, list) else None,
                      root_known_fields=sorted(k for k in ('available', 'unavailable', 'error', 'errors', 'errorCode', 'code', 'status', 'Status') if k in data))
        shapes = []
        for option in (available if isinstance(available, list) else [])[:4]:
            if not isinstance(option, dict): continue
            shape = {'known_fields': sorted(CONTENT_FIELDS.intersection(option))}
            for key, allowed in [('drmType', {'DRM_COMMON_ENCRYPTION', 'DRM_WIDEVINE', 'DRM_PLAYREADY', 'NONE'}),
                                 ('quality', {'SD', 'HD', 'FULLHD', 'UHD', '4K', 'HD720', 'HD1080', '720', '1080'}),
                                 ('distTechnology', {'DASH', 'HTTPSTREAMING', 'SMOOTHSTREAMING', 'HLS'})]:
                value = option.get(key)
                if isinstance(value, str): shape[key] = value if value in allowed else 'other'
            shapes.append(shape)
        if shapes: result['available_shapes'] = shapes
    except Exception as error:
        result.update(status='ERROR', reason=getattr(error, 'reason', 'vod_probe_failed'))
        details = getattr(error, 'details', {})
        if isinstance(details.get('http_status'), int): result['http_status'] = details['http_status']
        result.update(capture.summary)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', default='18487904_70025')
    args = parser.parse_args()
    result = {'probe_version': 2, 'account_tokens_printed': False, 'drm_keys_printed': False,
              'licence_requested': False, 'configuration_changed': False, 'checks': []}
    try:
        import canal_channels_test as channels
        from vod_api import VodApi, SameApiRedirect
        from version import APP_VERSION
        result['installed_version'] = APP_VERSION
        saved = channels.load_json(Path('/etc/canal-e2/session.json'))
        for name, agent in [('installed_vod_header', None), ('standard_browser_header', BROWSER_UA)]:
            result['checks'].append(probe_one(VodApi, SameApiRedirect, saved.get('authentication', {}),
                                              saved.get('device_id'), args.id, name, agent))
        channels.atomic_private_json(REPORT, result)
    except Exception as error:
        result['reason'] = getattr(error, 'reason', 'vod_probe_failed')
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if len(result['checks']) == 2 else 1


if __name__ == '__main__':
    raise SystemExit(main())
