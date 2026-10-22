#!/usr/bin/env python3
"""Probe additional public sources on the receiver; emit no source URLs or cookies."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.parse
import urllib.request

LOCAL=Path(__file__).resolve().parents[1]/'src/MKEkinoE2'
PLUGIN=LOCAL if (LOCAL/'worker.py').is_file() else Path('/usr/lib/enigma2/python/Plugins/Extensions/MKEkinoE2')
sys.path.insert(0,str(PLUGIN))
import catalogue
import resolver
import worker

REPORT=Path('/tmp/mk_ekino_sources_report.json')


def page_features(body):
    text=str(body)
    markers={
        'cloudflare_block':r'Attention Required! \| Cloudflare|Sorry, you have been blocked',
        'cloudflare_challenge':r'cf-chl-|challenges\.cloudflare\.com',
        'turnstile':r'turnstile',
        'recaptcha':r'g-recaptcha|recaptcha/api',
        'iframe':r'<iframe\b',
        'html5_source':r'<source\b',
        'playerjs':r'new\s+Playerjs\b',
        'jwplayer':r'jwplayer\s*\(',
        'packed_js':r'function\s*\(p,a,c,k,e,[dr]\)',
        'hls_field':r'["\']?hls["\']?\s*:',
        'file_field':r'["\']?file["\']?\s*:',
        'voe_payload':r'application/json',
        'hls_manifest':r'^\s*#EXTM3U',
    }
    return [key for key,pattern in markers.items() if re.search(pattern,text,re.I)]


class ProbeClient(resolver.Http):
    def __init__(self):
        super().__init__();self.observed=[]

    def getPage(self,url,params=None,post_data=None):
        params=dict(params or {});params['timeout']=12
        params['header']=dict(params.get('header',{}))
        params['header'].setdefault('Cache-Control','no-cache')
        ok,body=super().getPage(url,params,post_data)
        self.observed.append({'hostname':urllib.parse.urlsplit(self.meta.get('url','')).hostname,
                              'http_status':self.meta.get('status_code'),
                              'format_markers':page_features(body)})
        return ok,body


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


def safe_reason(error):
    text=str(error)
    return text if isinstance(error,(resolver.ResolveError,ValueError)) and re.fullmatch(r'[a-z_]{1,80}',text) else type(error).__name__


def probe_entry(entry,provider):
    client=ProbeClient();result={'provider':provider,'status':'ERROR','video_playback_tested':False}
    try:
        options=worker.source_options(client,dict(entry,provider=provider,provider_index=0))
        result['variant_count']=len(options)
        if options:
            result['media_check']=media_check(client,options[0])
            result['status']='MEDIA_REACHABLE' if result['media_check']['status']=='media_reachable' else 'VARIANTS_ONLY'
        else:result['reason']='no_variants'
    except Exception as error:
        result['reason']=safe_reason(error)
        if result['reason']=='source_access_denied':result['status']='BLOCKED'
    result['requests']=client.steps;result['page_formats']=client.observed
    return result


def save_report(report):
    descriptor,name=tempfile.mkstemp(prefix='mk-sources-',dir=REPORT.parent)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8') as output:json.dump(report,output,ensure_ascii=False,indent=2)
        os.replace(name,REPORT)
    finally:
        if os.path.exists(name):os.unlink(name)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--query',default='Król dopalaczy')
    parser.add_argument('--providers',default='wrzucaj,shvid,voe,mix');args=parser.parse_args()
    wanted=[p for p in args.providers.split(',') if p in ('wrzucaj','shvid','voe','mix')]
    report={'test':'additional_sources_v1','account_files_read':False,'configuration_changed':False,
            'video_playback_tested':False,'checks':[]}
    try:
        match=re.search(r"VERSION\s*=\s*['\"]([0-9.]+)",(PLUGIN/'plugin.py').read_text())
        report['installed_version']=match[1] if match else 'unknown'
        client=ProbeClient();entries=catalogue.browse(client,{'action':'search_results','query':args.query})
        entry=next((item for item in entries if item.get('action')=='sources'),None)
        if entry is None:raise ValueError('sample_title_not_found')
        body=catalogue.fetch(client,entry['url'])
        available=list(dict.fromkeys(item['provider'] for item in catalogue.source_items(body,entry)))
        report['available_providers']=available
        print('Test źródeł; pełny raport bez adresów strumieni: '+str(REPORT),flush=True)
        for provider in wanted:
            if provider not in available:continue
            print('Sprawdzam '+provider+'…',flush=True)
            result=probe_entry(entry,provider);report['checks'].append(result);save_report(report)
            last=result.get('page_formats',[])
            summary={'provider':provider,'status':result['status'],'reason':result.get('reason',''),
                     'variants':result.get('variant_count',0),
                     'last_host':last[-1].get('hostname') if last else None,
                     'http_status':last[-1].get('http_status') if last else None,
                     'format_markers':last[-1].get('format_markers') if last else []}
            print(json.dumps(summary,ensure_ascii=False),flush=True)
        report['status']='FINISHED'
    except Exception as error:
        report.update(status='ERROR',reason=safe_reason(error));print(json.dumps({'status':'ERROR','reason':report['reason']}),flush=True)
    finally:save_report(report)
    print('Raport: '+str(REPORT),flush=True)
    return 0 if report['status']=='FINISHED' else 1


if __name__=='__main__':raise SystemExit(main())
