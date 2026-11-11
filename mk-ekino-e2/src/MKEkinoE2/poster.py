# SPDX-License-Identifier: GPL-3.0-only
"""Small, bounded poster cache. Invoked outside the Enigma2 GUI process."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import tempfile
import threading
import urllib.parse
import urllib.request

CACHE=Path('/tmp/mk-ekino-posters')
MAX_BYTES=256*1024


def valid_url(url):
    parsed=urllib.parse.urlsplit(url)
    if (parsed.scheme!='https' or parsed.hostname!='ekino.ws' or parsed.username or parsed.password
            or parsed.port not in (None,443) or parsed.query or parsed.fragment
            or not re.fullmatch(r'/static/thumb/[A-Za-z0-9_-]+\.(?:jpg|jpeg|png)',parsed.path,re.I)):
        raise ValueError('invalid_poster_address')
    return url


class PosterRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        valid_url(newurl)
        return super().redirect_request(request,fp,code,msg,headers,newurl)


def fetch(url,cache=CACHE):
    valid_url(url);key=hashlib.sha256(url.encode()).hexdigest()
    cache.mkdir(mode=0o700,parents=True,exist_ok=True)
    for suffix in ('.jpg','.png'):
        path=cache/(key+suffix)
        if path.is_file() and 0<path.stat().st_size<=MAX_BYTES:return path
    request=urllib.request.Request(url,headers={'User-Agent':'MK-Ekino-E2','Referer':'https://ekino.ws/','Accept-Encoding':'identity'})
    with urllib.request.build_opener(PosterRedirect()).open(request,timeout=8) as response:
        valid_url(response.geturl());data=response.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:raise ValueError('poster_too_large')
    if data.startswith(b'\xff\xd8\xff'):suffix='.jpg'
    elif data.startswith(b'\x89PNG\r\n\x1a\n'):suffix='.png'
    else:raise ValueError('poster_not_image')
    descriptor,temporary=tempfile.mkstemp(prefix='fetch-',dir=cache)
    try:
        with os.fdopen(descriptor,'wb') as output:output.write(data)
        path=cache/(key+suffix);os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)
    files=sorted([p for p in cache.iterdir() if p.suffix in ('.jpg','.png')],key=lambda p:p.stat().st_mtime,reverse=True)
    for old in files[64:]:
        try:old.unlink()
        except OSError:pass
    return path


def main():
    parser=argparse.ArgumentParser();parser.add_argument('url',nargs='?');parser.add_argument('--batch');args=parser.parse_args()
    try:
        if args.batch:
            import json
            urls=json.loads(Path(args.batch).read_text())
            if not isinstance(urls,list) or len(urls)>4:return 1
            def download(url):
                try:print(json.dumps({'poster_ready':fetch(url).stem}),flush=True)
                except Exception:pass
            for offset in range(0,len(urls),2):
                threads=[threading.Thread(target=download,args=(url,),daemon=True) for url in urls[offset:offset+2]]
                for thread in threads:thread.start()
                for thread in threads:thread.join()
        else:fetch(args.url)
        return 0
    except Exception:return 1  # Optional artwork never prevents browsing or playback.


if __name__=='__main__':raise SystemExit(main())
