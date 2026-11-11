# SPDX-License-Identifier: GPL-3.0-only
"""Small private library keyed by catalogue URLs, never transient stream URLs."""
import json
import os
from pathlib import Path
import tempfile
import time
from urllib.parse import urlsplit

PATH=Path('/etc/mk-ekino-e2/library.json')
FIELDS=('title','action','url','icon','desc','synopsis','rating','rating_label',
        'rating_votes','year','language_version','series_url','series_title','season','episode','backdrop')


def entry_copy(entry):
    url=entry.get('url','')
    parsed=urlsplit(url) if isinstance(url,str) else None
    if (not parsed or parsed.scheme!='https' or parsed.netloc!='ekino.ws'
            or not parsed.path.startswith(('/movie/show/','/serie/show/','/serie/watch/'))
            or entry.get('action') not in ('sources','seasons')):return None
    return {k:v for k,v in entry.items() if k in FIELDS and isinstance(v,(str,int,float)) and not isinstance(v,bool)}


def stamp(seconds):
    seconds=max(0,int(seconds))
    return '%d:%02d:%02d' % (seconds//3600,seconds//60%60,seconds%60)


class Library:
    def __init__(self,path=None):self.path=Path(path) if path is not None else PATH

    def read(self):
        try:
            if self.path.stat().st_size>2*1024*1024:return {}
            data=json.loads(self.path.read_text())
            return data if isinstance(data,dict) else {}
        except (OSError,ValueError):return {}

    def write(self,data):
        self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        descriptor,name=tempfile.mkstemp(prefix='library-',dir=self.path.parent)
        try:
            with os.fdopen(descriptor,'w',encoding='utf-8') as output:
                json.dump(data,output,ensure_ascii=False)
            os.replace(name,self.path)
        finally:
            if os.path.exists(name):os.unlink(name)

    def settings(self):
        values=self.read().get('settings',{})
        if not isinstance(values,dict):values={}
        return {'auto_play':values.get('auto_play',True) is not False,
                'view':'list' if values.get('view')=='list' else 'tiles',
                'playback_service':5002 if values.get('playback_service',5002)==5002 else 4097}

    def setting(self,key,value):
        settings=self.settings()
        if key not in settings:return
        settings[key]=value
        data=self.read();data['settings']=settings;self.write(data)

    def favourites(self):
        values=self.read().get('favourites',[])
        return [copy for value in values[:100] if isinstance(value,dict) and (copy:=entry_copy(value))] if isinstance(values,list) else []

    def toggle(self,entry):
        copy=entry_copy(entry)
        if copy is None:return False
        data=self.read();values=self.favourites();present=any(v['url']==copy['url'] for v in values)
        data['favourites']=([v for v in values if v['url']!=copy['url']] if present else [copy]+values)[:100]
        self.write(data);return not present

    def progress(self,url):
        values=self.read().get('progress',{})
        value=values.get(url,{}) if isinstance(values,dict) else {}
        return value if isinstance(value,dict) else {}

    def record(self,entry,position,duration=0,completed=False):
        copy=entry_copy(entry)
        if copy is None:return
        position=max(0,min(int(position),7*86400));duration=max(0,min(int(duration),7*86400))
        if position<15 and not completed:return
        data=self.read();values=data.get('progress',{})
        if not isinstance(values,dict):values={}
        values[copy['url']]={'entry':copy,'position':position,'duration':duration,
                            'completed':bool(completed),'updated':time.time()}
        data['progress']=dict(sorted(((k,v) for k,v in values.items() if isinstance(v,dict)),
                             key=lambda pair:pair[1].get('updated',0),reverse=True)[:200])
        self.write(data)

    def continuing(self):
        values=self.read().get('progress',{})
        if not isinstance(values,dict):return []
        result=[]
        for value in sorted((v for v in values.values() if isinstance(v,dict)),key=lambda v:v.get('updated',0),reverse=True):
            entry=value.get('entry',{})
            if not isinstance(entry,dict) or value.get('completed') or not isinstance(value.get('position'),(int,float)):continue
            copy=entry_copy(entry)
            if copy and value['position']>=15:
                copy['progress_label']='Wznów od '+stamp(value['position']);result.append(copy)
        return result[:100]


def preferred_variant(options):
    def rank(option):
        language=str(option.get('language','')).lower().split('-')[0]
        pol=2 if language in ('pl','pol','polski','polish') else (1 if language in ('','und','auto') else 0)
        def number(key):
            try:return max(0,int(option.get(key,0)))
            except (ValueError,TypeError):return 0
        height=number('height');area=number('width')*height or height*height
        return pol,area,number('bitrate')
    return max(range(len(options)),key=lambda i:rank(options[i])) if options else None
