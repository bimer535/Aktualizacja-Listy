#!/usr/bin/env python3
"""Background catalogue/resolver worker; only constructed events reach the GUI."""
import argparse
import html
import json
import os
from pathlib import Path
import re
import signal
import tempfile
import time
import urllib.parse

import catalogue
import access_cache
import resolver
from watchstate import preferred_variant
from relay import Relay
from other_sources import OtherSources

REPORT=Path('/tmp/mk_ekino_report.json')


def emit(stage,**fields):
    print(json.dumps(dict(stage=stage,**fields),ensure_ascii=False),flush=True)


def atomic(path,data):
    fd,name=tempfile.mkstemp(prefix='mk-ekino-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as out:json.dump(data,out,ensure_ascii=False)
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def source_options(client,item):
    provider=item['provider']
    if provider not in ('player','voe','mix','wrzucaj','shvid','upzone'):raise resolver.ResolveError('source_not_supported')
    resolver.ACTIVE_HTTP=client
    title=item['url']
    body=catalogue.fetch(client,title)
    keys=list(dict.fromkeys(re.findall(r"ShowPlayer\(['\"]"+re.escape(provider)+r"['\"],\s*['\"]([^'\"]+)['\"]\)",body)))
    index=item.get('provider_index',0)
    if type(index) is not int or not 0<=index<len(keys):raise resolver.ResolveError('player_source_not_found')
    current=catalogue.BASE+'watch/f/'+provider+'/'+urllib.parse.quote(keys[index],safe='')
    parent=title;seen=set()
    for _ in range(6):
        if current in seen:raise resolver.ResolveError('embed_redirect_loop')
        seen.add(current)
        host=urllib.parse.urlsplit(current).hostname or ''
        wrapper=host=='ekino.ws' or host=='ekino.link' or host.endswith('.ekino.link')
        if provider in ('voe','mix','wrzucaj','shvid','upzone') and not wrapper:
            parser=OtherSources(client)
            method={'voe':parser.parserVOESX,'mix':parser.parserMIXDROP,'wrzucaj':parser.parserSST,'shvid':parser.parserSST,'upzone':parser.parserUPZONECC}[provider]
            result=method(resolver.URL(current,{'Referer':parent}))
            if not result:
                if client.meta.get('status_code')==403:raise resolver.ResolveError('source_access_denied')
                raise resolver.ResolveError('source_returned_no_variants')
            for option in result:
                meta=dict(getattr(option['url'],'meta',{}))
                meta.setdefault('User-Agent',client.getDefaultHeader()['User-Agent'])
                meta.setdefault('Referer',current)
                option['url']=resolver.URL(option['url'],meta)
            return result
        if provider=='player' and host=='mfw09.org':
            engine=resolver.Byse(client)
            engine.BYSE_ACCESS=access_cache.load()
            cached=len(engine.BYSE_ACCESS)
            started=time.monotonic()
            try:
                result=engine.parserBYSE(resolver.URL(current,{'Referer':parent}))
            finally:
                try:access_cache.save(engine.BYSE_ACCESS)
                except OSError:pass
                client.source_metrics={'cached_access_candidates':cached,'verification':engine.pow_stats,
                                       'elapsed_ms':round((time.monotonic()-started)*1000)}
            if not result:raise resolver.ResolveError('source_returned_no_variants')
            return result
        ok,body=client.getPage(current,{'header':{'Referer':parent}})
        if client.meta.get('status_code')==403 or 'cf-chl-' in body or 'Attention Required! | Cloudflare' in body:
            raise resolver.ResolveError('source_access_denied')
        if not ok:raise resolver.ResolveError('watch_or_embed_http_error')
        final=client.meta.get('url',current)
        if urllib.parse.urlsplit(final).hostname=='mfw09.org':current=final;continue
        target=None
        for pattern in [r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*target=',r'<iframe\b[^>]*src=["\']([^"\']+)["\']']:
            match=re.search(pattern,body,re.I)
            if match:target=urllib.parse.urljoin(final,html.unescape(match[1]));break
        if not target:raise resolver.ResolveError('no_normal_embed_link')
        parent,current=final,target
    raise resolver.ResolveError('embed_chain_too_long')


def label(option,index):
    language={'pl':'Polski','pol':'Polski','en':'English','eng':'English'}.get(option.get('language'),option.get('language') or 'Auto')
    if option.get('width') and option.get('height'):
        return '[%s] bitrate: %s res: %sx%s %s' % (language,option.get('bitrate',0),option['width'],option['height'],option.get('codecs',''))
    return '[%s] %s' % (language,option.get('name') or ('Wariant %d' % (index+1)))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--request',type=Path,required=True)
    parser.add_argument('--result',type=Path,required=True)
    parser.add_argument('--control',type=Path,required=True)
    args=parser.parse_args()
    def stop(*_):raise KeyboardInterrupt
    signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
    relay=None;report=None;client=resolver.Http();stage='prepare';item={}
    try:
        request=json.loads(args.request.read_text())
        item=request['item']
        if item['action']!='resolve':
            stage='catalogue';emit(stage)
            entries=catalogue.browse(client,item)
            atomic(args.result,{'items':entries});emit('catalogue_ready',count=len(entries));return 0
        stage='resolve';emit(stage)
        options=source_options(client,item)
        if not options:raise resolver.ResolveError('source_returned_no_variants')
        if item.get('auto_quality'):
            selection=preferred_variant(options)
            emit('variant_selected',language=options[selection].get('language','Auto'),height=options[selection].get('height',0))
        else:
            atomic(args.result,{'variants':[label(v,i) for i,v in enumerate(options)]})
            emit('choose_variant',count=len(options))
            deadline=time.monotonic()+900
            selection=None
            while time.monotonic()<deadline:
                if args.control.is_file():
                    choice=json.loads(args.control.read_text())
                    selection=choice.get('index');break
                time.sleep(.2)
        if isinstance(selection,bool) or not isinstance(selection,int) or not 0<=selection<len(options):
            raise resolver.ResolveError('variant_selection_cancelled')
        stage='playback_relay';relay=Relay(options[selection],client)
        # The native Enigma2 player receives only a loopback URL.
        selected={key:options[selection].get(key) for key in ('width','height','language','codecs','bitrate')}
        report={'status':'RELAY_READY','version':'0.2.9','requests':client.steps,
                'source_provider':item.get('provider',''),'source_metrics':getattr(client,'source_metrics',{}),
                'playback_service':5002 if item.get('playback_service')==5002 else 4097,
                'selected_variant':selected,'video_playback_confirmed':False,'e2i_imported':False}
        report['relay']=relay.snapshot();atomic(REPORT,report)
        emit('play_ready',url=relay.url)
        while True:
            time.sleep(2)
            report['relay']=relay.snapshot();atomic(REPORT,report)
    except KeyboardInterrupt:emit('cancelled');return 130
    except Exception as error:
        reason=str(error) if isinstance(error,(resolver.ResolveError,ValueError)) and re.fullmatch(r'[a-z_]{1,80}',str(error)) else type(error).__name__
        atomic(REPORT,{'status':'ERROR','version':'0.2.9','stage':stage,'reason':reason,'requests':client.steps,'source_provider':item.get('provider',''),'source_metrics':getattr(client,'source_metrics',{}),'e2i_imported':False})
        emit('error',reason=reason);return 1
    finally:
        if relay:
            relay.close()
            if report is not None:
                report['status']='RELAY_STOPPED'
                report['relay']=relay.snapshot()
                try:atomic(REPORT,report)
                except OSError:pass


if __name__=='__main__':raise SystemExit(main())
