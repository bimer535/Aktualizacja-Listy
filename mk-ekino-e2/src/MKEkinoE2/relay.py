"""Loopback-only HLS relay, preserving the chosen audio/video rendition."""
import re
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import resolver


class Relay:
    def __init__(self, option, client):
        self.option=option
        self.client=client
        self.token=secrets.token_urlsafe(24)
        self.targets={};self.reverse={};self.lock=threading.RLock()
        self.metrics={'local_requests':0,'upstream_requests':0,'playlists':0,'media_bytes':0,'errors':0,
                      'last_http_status':0,'last_error':'','last_content_type':''}
        self.headers={k:v for k,v in getattr(option['url'],'meta',{}).items()
                      if k in ('User-Agent','Referer','Origin')}
        self.headers['Accept-Encoding']='identity'
        owner=self
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.0'
            def log_message(self,*args):pass
            def do_GET(self):owner.serve(self)
            def do_HEAD(self):owner.serve(self,head=True)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.daemon_threads=True
        self.port=self.server.server_port
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def snapshot(self):
        with self.lock:return dict(self.metrics)

    def record(self,**values):
        with self.lock:
            for name,value in values.items():
                if name in ('local_requests','upstream_requests','playlists','media_bytes','errors'):self.metrics[name]+=value
                else:self.metrics[name]=value

    def route(self,url,playlist=False,extension=None):
        value=str(url)
        suffix='.m3u8' if playlist else (extension or '')
        if suffix not in ('','.m3u8','.ts','.m4s','.mp4','.m4a','.aac','.mp3','.ac3','.ec3','.vtt','.key'):raise ValueError('invalid_relay_extension')
        with self.lock:
            identity=(value,suffix)
            if identity not in self.reverse:
                # A bounded VOD playlist may have thousands of segment URLs.
                if len(self.targets)>=100000:raise ValueError('relay_resource_limit')
                key=str(len(self.targets))+suffix
                self.targets[key]=value;self.reverse[identity]=key
            return 'http://127.0.0.1:%d/%s/%s' % (self.port,self.token,self.reverse[identity])

    @property
    def url(self):
        meta=getattr(self.option['url'],'meta',{})
        suffix='m3u8' if '.m3u8' in str(self.option['url']).lower() or meta.get('video_url') or meta.get('iptv_proto')=='m3u8' or self.option.get('name')=='HLS' else 'mp4'
        return 'http://127.0.0.1:%d/%s/master.%s' % (self.port,self.token,suffix)

    def master(self):
        option=self.option;meta=getattr(option['url'],'meta',{})
        if not meta.get('video_url'):return None
        lines=['#EXTM3U','#EXT-X-VERSION:6']
        audio=meta.get('audio_url')
        if audio:
            lang=option.get('language','')
            lines.append('#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="selected",NAME="%s",LANGUAGE="%s",DEFAULT=YES,AUTOSELECT=YES,URI="%s"' %
                         (lang or 'Audio',lang,self.route(audio,playlist=True)))
        attrs=['BANDWIDTH='+str(max(1,int(option.get('bitrate',0))))]
        if option.get('width') and option.get('height'):
            attrs.append('RESOLUTION=%dx%d' % (option['width'],option['height']))
        if option.get('codecs'):attrs.append('CODECS="'+option['codecs']+'"')
        if audio:attrs.append('AUDIO="selected"')
        lines.extend(['#EXT-X-STREAM-INF:'+','.join(attrs),self.route(meta['video_url'],playlist=True)])
        return ('\n'.join(lines)+'\n').encode()

    def media_extension(self,url,fragmented=False):
        suffix=urllib.parse.urlsplit(url).path.lower().rsplit('/',1)[-1].rsplit('.',1)
        suffix='.'+suffix[-1] if len(suffix)>1 else ''
        if suffix in ('.ts','.m4s','.mp4','.m4a','.aac','.mp3','.ac3','.ec3','.vtt'):return suffix
        # Some CDNs mask MPEG-TS as CSS/images or omit an extension. Keep the
        # upstream URL untouched; provide media names only on the local relay.
        return '.m4s' if fragmented else '.ts'

    def rewrite(self,body,base):
        lines=[];variant=False
        source=body.decode('utf-8-sig').splitlines()
        fragmented=any(line.startswith('#EXT-X-MAP:') for line in source)
        for line in source:
            if line and not line.startswith('#'):
                target=urllib.parse.urljoin(base,line.strip())
                playlist=variant or urllib.parse.urlsplit(target).path.lower().endswith('.m3u8')
                line=self.route(target,playlist=playlist,extension=None if playlist else self.media_extension(target,fragmented))
                variant=False
            elif line.startswith('#'):
                is_playlist=line.startswith(('#EXT-X-MEDIA:','#EXT-X-I-FRAME-STREAM-INF:','#EXT-X-RENDITION-REPORT:'))
                def resource(match):
                    target=urllib.parse.urljoin(base,match[1])
                    if is_playlist:extension=None
                    elif line.startswith(('#EXT-X-KEY:','#EXT-X-SESSION-KEY:')):extension='.key'
                    elif line.startswith('#EXT-X-MAP:'):extension='.mp4'
                    else:extension=self.media_extension(target,fragmented)
                    return 'URI="'+self.route(target,playlist=is_playlist,extension=extension)+'"'
                line=re.sub(r'URI="([^\"]+)"',resource,line)
                variant=line.startswith('#EXT-X-STREAM-INF:') or variant
            lines.append(line)
        return ('\n'.join(lines)+'\n').encode()

    def serve(self,request,head=False):
        prefix='/'+self.token+'/'
        if not request.path.startswith(prefix):request.send_error(404);return
        self.record(local_requests=1)
        key=request.path[len(prefix):]
        if key in ('master.m3u8','master.mp4'):
            data=self.master()
            if data is not None:
                request.send_response(200);request.send_header('Content-Type','application/vnd.apple.mpegurl')
                request.send_header('Content-Length',str(len(data)));request.end_headers()
                if not head:request.wfile.write(data)
                return
            target=str(self.option['url'])
        else:
            with self.lock:target=self.targets.get(key)
        if not target:request.send_error(404);return
        try:
            sent=False
            headers=dict(self.headers)
            is_playlist=key.endswith('.m3u8') or urllib.parse.urlsplit(target).path.lower().endswith('.m3u8')
            if request.headers.get('Range') and not is_playlist:headers['Range']=request.headers['Range']
            upstream=urllib.request.Request(resolver.checked_url(target),headers=headers,method='HEAD' if head else 'GET')
            self.record(upstream_requests=1)
            with self.client.opener.open(upstream,timeout=25) as response:
                kind=response.headers.get('Content-Type','application/octet-stream')
                self.record(last_http_status=response.code,last_content_type=kind.split(';')[0][:80])
                first=b'' if head else response.read(512)
                playlist=(key.endswith('.m3u8') or urllib.parse.urlsplit(response.geturl()).path.lower().endswith('.m3u8') or 'mpegurl' in kind.lower() or first.lstrip(b'\xef\xbb\xbf\r\n\t ').startswith(b'#EXTM3U'))
                if playlist and not head:
                    raw=first+response.read(resolver.MAX_PAGE+1-len(first))
                    if len(raw)>resolver.MAX_PAGE:raise ValueError('playlist_too_large')
                    if not raw.lstrip(b'\xef\xbb\xbf\r\n\t ').startswith(b'#EXTM3U'):raise ValueError('invalid_hls_response')
                    data=self.rewrite(raw,response.geturl())
                    self.record(playlists=1)
                    request.send_response(200);request.send_header('Content-Type','application/vnd.apple.mpegurl')
                    request.send_header('Content-Length',str(len(data)));request.end_headers();sent=True;request.wfile.write(data)
                else:
                    if playlist:kind='application/vnd.apple.mpegurl'
                    if len(first)>376 and first[0]==0x47 and first[188]==0x47 and first[376]==0x47:kind='video/mp2t'
                    elif len(first)>=8 and first[4:8] in (b'ftyp',b'styp',b'moof'):kind='video/mp4'
                    request.send_response(response.code)
                    request.send_header('Content-Type',kind)
                    for name in ['Content-Length','Content-Range','Accept-Ranges']:
                        if response.headers.get(name):request.send_header(name,response.headers[name])
                    request.end_headers();sent=True
                    if not head:
                        request.wfile.write(first);self.record(media_bytes=len(first))
                        while True:
                            data=response.read1(65536) if hasattr(response,'read1') else response.read(65536)
                            if not data:break
                            request.wfile.write(data);self.record(media_bytes=len(data))
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception as error:
            self.record(errors=1,last_error=type(error).__name__)
            if isinstance(error,urllib.error.HTTPError):self.record(last_http_status=error.code)
            # Do not print request URLs or raw upstream exception text.
            try:
                if not sent:request.send_error(502)
            except OSError:pass

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
