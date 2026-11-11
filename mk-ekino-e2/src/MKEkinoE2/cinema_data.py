# SPDX-License-Identifier: GPL-3.0-only
"""Optional public artwork metadata. Playback stays on the 0.2.11 catalogue."""
import json
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import urlencode, urlsplit

API='https://premiumsmart.eu/api/v1/'
CACHE=Path('/tmp/mk-kino-artwork.json')

def title_key(value):
    value=re.sub(r'\s*[-–/]\s*(?:HD|FHD|UHD|4K)\b.*$', '', str(value),flags=re.I)
    value=value.split(' / ')[0]
    return re.sub(r'[^a-z0-9ąćęłńóśźż]+',' ',unicodedata.normalize('NFKC',value).lower()).strip()

def image_url(value,wide=False):
    if not isinstance(value,str):return ''
    p=urlsplit(value)
    if p.scheme!='https' or p.username or p.password or p.port not in (None,443) or p.query or p.fragment:return ''
    if p.hostname=='image.tmdb.org' and re.fullmatch(r'/t/p/(?:original|w\d+)/[A-Za-z0-9_-]+\.(?:jpg|png)',p.path):
        return re.sub(r'/t/p/(?:original|w\d+)/','/t/p/'+('w1280' if wide else 'w342')+'/',value)
    return ''

def metadata(client):
    try:
        if CACHE.stat().st_size<1024*1024 and time.time()-CACHE.stat().st_mtime<3600:
            values=json.loads(CACHE.read_text())
            if isinstance(values,list):return values
    except (OSError,ValueError):pass
    values=[]
    try:
        url=API+'channel/filmy?'+urlencode({'perPage':60,'page':1,'order':'created_at:desc'})
        ok,body=client.getPage(url,{'header':{'Accept':'application/json','Referer':'https://premiumsmart.eu/'},'timeout':6})
        rows=json.loads(body).get('channel',{}).get('content',{}).get('data',[]) if ok else []
        if isinstance(rows,list):
            for row in rows[:60]:
                if not isinstance(row,dict) or row.get('is_series'):continue
                year=str(row.get('year') or row.get('release_date') or '')[:4]
                wide=image_url(row.get('backdrop'),True)
                if wide:values.append({'key':title_key(row.get('name','')),'year':year,'backdrop':wide})
        if values:
            temporary=CACHE.with_suffix('.tmp');temporary.write_text(json.dumps(values));temporary.chmod(0o600);temporary.replace(CACHE)
    except Exception:pass  # Optional pictures never block the real catalogue.
    return values

def enrich(entries,values):
    lookup={(v.get('key'),v.get('year')):v.get('backdrop') for v in values if isinstance(v,dict)}
    for entry in entries:
        for name in (entry.get('title',''),entry.get('original_title','')):
            wide=image_url(lookup.get((title_key(name),str(entry.get('year','')))),True)
            if wide:entry['backdrop']=wide;break
    return entries

def panorama(entries):
    return [e for e in entries if e.get('action')=='sources' and str(e.get('year'))=='2026' and image_url(e.get('backdrop'),True)][:12]
