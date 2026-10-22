#!/usr/bin/env python3
"""Receiver-side catalogue/source probe, without accounts, cookies or stream URLs in output."""
import argparse,json,re,sys,urllib.parse,urllib.request
from pathlib import Path
LOCAL=Path(__file__).resolve().parents[1]/'src/MKPremiumSmartE2'
PLUGIN=LOCAL if (LOCAL/'worker.py').is_file() else Path('/usr/lib/enigma2/python/Plugins/Extensions/MKPremiumSmartE2')
sys.path.insert(0,str(PLUGIN))
import catalogue,resolver,worker

def media_check(client,option):
    original=option['url'];meta=getattr(original,'meta',{})
    headers={key:value for key,value in meta.items() if key in ('User-Agent','Referer','Origin') and isinstance(value,str)}
    target=meta.get('video_url') or str(original)
    was_hls=False
    for _ in range(4):
        if '.m3u8' not in urllib.parse.urlsplit(target).path.lower() and not meta.get('iptv_proto')=='m3u8':break
        ok,body=client.getPage(resolver.URL(target,headers),{'header':headers})
        if not ok or not str(body).lstrip().startswith('#EXTM3U'):return {'status':'manifest_unavailable'}
        was_hls=True
        child=next((line.strip() for line in str(body).splitlines() if line.strip() and not line.startswith('#')),None)
        if not child:return {'status':'empty_manifest'}
        target=urllib.parse.urljoin(target,child)
        if '.m3u8' not in urllib.parse.urlsplit(target).path.lower():break
    request=urllib.request.Request(resolver.checked_url(target),headers=dict(headers,Range='bytes=0-2047'))
    with client.opener.open(request,timeout=12) as response:
        data=response.read(2048);kind=response.headers.get('Content-Type','').lower()
        result={'http_status':response.code,'content_type':kind.split(';')[0],
                'hostname':urllib.parse.urlsplit(response.geturl()).hostname,'bytes_read':len(data)}
    signature=''
    if len(data)>=8 and data[4:8] in (b'ftyp',b'styp',b'moof'):signature='mp4'
    elif len(data)>188 and data[0]==0x47 and data[188]==0x47:signature='mpeg_ts'
    elif data.startswith(b'\x1aE\xdf\xa3'):signature='webm'
    elif was_hls and data and not any(marker in kind for marker in ('html','json','mpegurl')) and not data.lstrip().startswith((b'<',b'#EXTM3U')):signature='hls_segment'
    result.update(status='media_reachable' if signature and result['http_status'] in (200,206) else 'not_confirmed_media',media_signature=signature)
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--year');parser.add_argument('--version',default='Lektor PL');parser.add_argument('--media',action='store_true');parser.add_argument('--provider',choices=['byse','streamtape','voe','mix']);args=parser.parse_args()
    client=resolver.Http();report={'video_playback_tested':False,'account_files_read':False}
    try:
        entries=catalogue.browse(client,{'action':'movies','kind':'filmy','year':args.year,'version':args.version,'order':'release_date:desc'})
        movies=[entry for entry in entries if entry.get('action')=='sources']
        report.update(status='CATALOGUE_OK',movie_count=len(movies),years=sorted(set(e['year'] for e in movies)),versions=sorted(set(e['language_version'] for e in movies)))
        if movies:
            sources=catalogue.source_items(client,movies[0]);report['source_providers']=[entry['provider'] for entry in sources]
            if args.provider:sources=[entry for entry in sources if entry['provider']==args.provider]
            if args.media and sources:
                options=worker.source_options(client,sources[0]);report['variant_count']=len(options)
                report['media_check']=media_check(client,options[0]);report['status']='MEDIA_REACHABLE' if report['media_check']['status']=='media_reachable' else 'VARIANTS_ONLY'
    except Exception as error:
        reason=str(error)
        report.update(status='ERROR',reason=reason if isinstance(error,(ValueError,resolver.ResolveError)) and re.fullmatch('[a-z_]{1,80}',reason) else type(error).__name__)
    report['requests']=client.steps
    worker.atomic(Path('/tmp/mk_premiumsmart_probe.json'),report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['status']!='ERROR' else 1

if __name__=='__main__':raise SystemExit(main())
