#!/usr/bin/env python3
"""Background catalogue process. Never reads the account or plays video."""
import argparse
import json
import sys
import vod_data as vod


def main():
    p = argparse.ArgumentParser()
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--request')
    group.add_argument('--search')
    args = p.parse_args()
    try:
        result = vod.search(args.search) if args.search is not None else vod.load_page(json.loads(args.request))
        print(json.dumps({'stage': 'vod_loaded', 'page': result}, ensure_ascii=False), flush=True)
        return 0
    except Exception as error:
        reason = error.reason if isinstance(error, vod.VodError) else 'vod_catalogue_invalid_response'
        details = getattr(error, 'details', {})
        event = {'stage': 'error', 'reason': reason}
        if isinstance(details.get('http_status'), int):
            event['http_status'] = details['http_status']
        print(json.dumps(event), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
