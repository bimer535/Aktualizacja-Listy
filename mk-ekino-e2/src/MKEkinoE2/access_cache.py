"""Short-lived local cache of verification explicitly granted by the source."""
import json
import math
import os
from pathlib import Path
import tempfile
import time
import urllib.parse

PATH=Path('/tmp/mk-ekino-access.json')
MAX_LIFETIME=1800


def valid(data,now=None):
    now=time.time() if now is None else now
    out={}
    if not isinstance(data,dict):return out
    for origin,value in list(data.items())[:12]:
        if not isinstance(origin,str):continue
        try:
            url=urllib.parse.urlsplit(origin)
            if (url.scheme!='https' or not url.hostname or '.' not in url.hostname
                    or url.path!='/' or url.query or url.fragment or url.username
                    or url.password or url.port not in (None,443)):continue
        except ValueError:continue
        if not isinstance(value,(list,tuple)) or len(value)!=3:continue
        expiry,fp,token=value
        if isinstance(expiry,bool) or not isinstance(expiry,(float,int)) or not math.isfinite(expiry) or not now<expiry<=now+MAX_LIFETIME:continue
        if not isinstance(fp,dict) or not isinstance(token,str) or not 1<=len(token)<=16384:continue
        allowed={k:fp[k] for k in ('token','viewer_id','device_id','confidence') if k in fp}
        if not all(isinstance(allowed.get(k),str) and 0<len(allowed[k])<=16384 for k in ('token','viewer_id','device_id')):continue
        confidence=allowed.get('confidence')
        if not isinstance(confidence,(float,int)) or isinstance(confidence,bool) or not math.isfinite(confidence) or not 0<=confidence<=1:continue
        out[origin]=(expiry,allowed,token)
    return out


def load(path=PATH):
    try:
        if path.stat().st_size>256*1024:return {}
        with path.open(encoding='utf-8') as stream:return valid(json.load(stream))
    except (OSError,ValueError):return {}


def save(data,path=PATH):
    values=valid(data)
    descriptor,name=tempfile.mkstemp(prefix='mk-ekino-access-',dir=path.parent)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8') as output:json.dump(values,output,separators=(',',':'))
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)
