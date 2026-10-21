#!/usr/bin/env python3
"""Read-only VOD API shape probe, run after installing MK Canal+ E2 0.5.0.

Does not start conso/view, request a licence, play video, or print credentials.
"""
import argparse
import json
from pathlib import Path
import re
import sys

PLUGIN = Path('/usr/lib/enigma2/python/Plugins/Extensions/CanalE2Test')
sys.path.insert(0, str(PLUGIN))
REPORT = Path('/tmp/mk_canal_vod_probe.json')


def fields(value):
    return sorted(k for k in value if isinstance(k, str) and re.fullmatch(r'[@A-Za-z_][@A-Za-z_0-9-]{0,60}', k))[:50]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', default='18487904_70025')
    args = parser.parse_args()
    result = {'probe_version': 1, 'status': 'ERROR', 'account_tokens_printed': False,
              'drm_keys_printed': False, 'licence_requested': False, 'video_playback_tested': False}
    try:
        import canal_channels_test as channels
        from vod_api import VodApi
        saved = channels.load_json(Path('/etc/canal-e2/session.json'))
        client = VodApi(saved.get('authentication', {}), saved.get('device_id'))
        data = client.playset(args.id)
        result['root_fields'] = fields(data)
        available = data.get('available')
        result['available_count'] = len(available) if isinstance(available, list) else None
        result['available_shapes'] = []
        for option in (available or [])[:8]:
            if not isinstance(option, dict):
                continue
            shape = {'fields': fields(option)}
            for key in ('drmType', 'distTechnology', 'quality', 'distMode', 'comMode'):
                value = option.get(key)
                if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_ .-]{1,80}', value):
                    shape[key] = value
            result['available_shapes'].append(shape)
        for key in ('Status', 'status', 'errorCode', 'code'):
            value = data.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                result.setdefault('service_codes', {})[key] = value
        result['status'] = 'PLAYSET_RECEIVED'
        channels.atomic_private_json(REPORT, result)
    except Exception as error:
        result['reason'] = getattr(error, 'reason', 'vod_probe_failed')
        details = getattr(error, 'details', {})
        if isinstance(details.get('http_status'), int):
            result['http_status'] = details['http_status']
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PLAYSET_RECEIVED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
