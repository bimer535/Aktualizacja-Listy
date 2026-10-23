#!/usr/bin/env python3
"""Bounded CDA catalogue/media test; no credentials, cookies or stream URLs printed."""
import argparse
import json
from pathlib import Path
import re
import sys
import urllib.request

LOCAL=Path(__file__).resolve().parents[1]/'src/MKCDAE2'
sys.path.insert(0,str(LOCAL if LOCAL.is_dir() else Path('/usr/lib/enigma2/python/Plugins/Extensions/MKCDAE2')))
import catalogue
import cda
import resolver
import worker


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--media',action='store_true');parser.add_argument('--url');args=parser.parse_args()
    client=resolver.Http();report={'video_playback_tested':False,'account_credentials_read':False}
    try:
        entries=catalogue.browse(client,{'action':'movies','access':'2','order':'new','page':1})
        films=[value for value in entries if value['action']=='sources']
        report.update(status='CATALOGUE_OK',film_count=len(films),sample_titles=[value['title'] for value in films[:5]],
                      all_rows_free=all('darmo' in value['access_label'].lower() for value in films))
        if args.media:
            entry={'url':cda.video_url(args.url)} if args.url else (films[0] if films else None)
            if not entry:raise ValueError('catalogue_empty')
            options=cda.options(client,dict(entry,auto_quality=True));option=options[0]
            report.update(variant_count=len(options),selected_height=option.get('height',0))
            if '.m3u8' in str(option['url']):report['status']='HLS_VARIANT_READY'
            else:
                headers={key:value for key,value in getattr(option['url'],'meta',{}).items() if key in ('User-Agent','Referer','Origin')}
                with client.opener.open(urllib.request.Request(str(option['url']),headers=dict(headers,Range='bytes=0-2047')),timeout=15) as response:
                    data=response.read(2048)
                    report.update(http_status=response.code,content_type=response.headers.get('Content-Type','').split(';')[0],bytes_read=len(data),mp4_signature=data[4:8]==b'ftyp')
                report['status']='MEDIA_REACHABLE' if report['mp4_signature'] else 'MEDIA_NOT_CONFIRMED'
    except Exception as error:
        reason=str(error)
        report.update(status='ERROR',reason=reason if isinstance(error,(ValueError,resolver.ResolveError)) and re.fullmatch('[a-z_]{1,80}',reason) else type(error).__name__)
    report['requests']=client.steps;worker.atomic(Path('/tmp/mk_cda_probe.json'),report)
    print(json.dumps(report,ensure_ascii=False,indent=2));return int(report['status']=='ERROR')


if __name__=='__main__':raise SystemExit(main())
