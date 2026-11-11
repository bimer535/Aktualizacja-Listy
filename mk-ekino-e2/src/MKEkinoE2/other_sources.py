# SPDX-License-Identifier: GPL-3.0-only
"""Public VOE and MixDrop parsers with standalone, non-executing helpers.

Parser methods come from e2iplayer-2026.10.18.05, libs/urlparser.py.
The packed-JavaScript reader substitutes strings; it never evaluates JS.
"""
import ast
import base64
import html
import re
from urllib.parse import urljoin, urlsplit
from resolver import (urlparser,SetIPTVPlayerLastHostError,printDBG,_,json_loads,
                      getDirectM3U8Playlist,ResolveError,checked_url)


# Python equivalent of cnc(atob(blob)) from the public upzonecc.byte.
# Verified against the original Duktape decoder, including every byte value.
UPZONE_TABLE=' zyx-   srqpwvutkjihonmlcba gfed ZYX_   SRQPWVUTKJIHONMLCBA GFED :98? = 32107654    /.'


def decode_upzone(blob):
    if not isinstance(blob,str) or not 4<=len(blob)<=4096:
        raise ValueError('upzone_payload_invalid')
    raw=base64.b64decode(blob+'='*(-len(blob)%4),validate=True)
    return ''.join(UPZONE_TABLE[value] for value in raw if value<len(UPZONE_TABLE))


def ensure_str(value):
    return value.decode('utf-8') if isinstance(value,bytes) else str(value)


class ph:
    @staticmethod
    def search(text,pattern):
        match=re.search(pattern,text,re.S)
        return match.groups() if match else ('',)


def get_packed_data(text):
    literal=r'''(?:'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")'''
    pattern=re.compile(r'\}\s*\(\s*('+literal+r'),\s*(\d+),\s*(\d+),\s*('+literal+r')\.split\([\'\"]\|[\'\"]\)',re.S)
    for _hop in range(5):
        match=pattern.search(text)
        if not match:break
        payload=ast.literal_eval(match[1]);radix=int(match[2]);count=int(match[3]);words=ast.literal_eval(match[4]).split('|')
        if not 2<=radix<=62 or count>100000 or len(payload)>2*1024*1024:return ''
        alphabet='0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        def replace(token):
            value=0
            for char in token[0]:
                digit=alphabet.find(char)
                if digit<0 or digit>=radix:return token[0]
                value=value*radix+digit
                if value>=count:return token[0]
            return words[value] if value<len(words) and words[value] else token[0]
        decoded=re.sub(r'\b[0-9A-Za-z]+\b',replace,payload)
        text=text[:match.start()]+decoded+text[match.end():]
    return text


class OtherSources:
    def __init__(self,client):self.cm=client

    def parserUPZONECC(self,baseUrl):
        """Public Upzone embed flow, with a local Python string decoder."""
        host=urlsplit(str(baseUrl)).hostname or ''
        if host!='upzone.cc' and not host.endswith('.upzone.cc'):
            raise ResolveError('upzone_address_not_supported')
        headers=self.cm.getDefaultHeader()
        headers['Referer']=getattr(baseUrl,'meta',{}).get('Referer',str(baseUrl))

        def fetch(url):
            ok,body=self.cm.getPage(url,{'header':headers})
            status=self.cm.meta.get('status_code')
            if status==403 or re.search(r'cf-chl-|challenges\.cloudflare\.com|Attention Required! \| Cloudflare',body,re.I):
                raise ResolveError('source_access_denied')
            if not ok:raise ResolveError('watch_or_embed_http_error')
            return str(body),self.cm.meta.get('url',str(url))

        body,page=fetch(baseUrl)
        if not urlsplit(page).path.startswith('/embed/'):
            file_id=urlsplit(page).path.rstrip('/').rsplit('/',1)[-1]
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',file_id):
                raise ResolveError('upzone_address_not_supported')
            extra,page=fetch(urljoin(page,'/embed/'+file_id))
            body+='\n'+extra
        # Never execute scripts from a host page. Decode only bounded literals.
        blobs=re.findall(r'''['"]([A-Za-z0-9+/]{24,4096}={0,2})['"]''',body)
        media=[]
        for blob in blobs[:64]:
            try:
                decoded=decode_upzone(blob).strip()
                if not decoded or re.search(r'[\s<>"\x00-\x1f]',decoded):continue
                if not decoded.startswith(('https://','//','/')):continue
                url=checked_url(urljoin(page,html.unescape(decoded)))
            except (ValueError,ResolveError):continue
            if url not in media:media.append(url)
        if not media:
            text=html.unescape(re.sub(r'<[^>]*>',' ',body)).lower()
            if ('transfer' in text and 'wyczerpan' in text) or re.search(r'(?:tylko|wymagane|wymaga)\s+(?:konto\s+)?premium',text):
                raise ResolveError('upzone_transfer_limit')
            raise ResolveError('upzone_payload_not_found')
        meta={'User-Agent':headers['User-Agent'],'Referer':page,
              'Origin':urlparser.getDomain(page,False).rstrip('/')}
        result=[]
        for source in media:
            url=urlparser.decorateUrl(source,meta)
            if '.m3u8' in urlsplit(source).path.lower():result.extend(getDirectM3U8Playlist(url))
            else:result.append({'name':'MP4','url':url})
        return result

    def parserSST(self,baseUrl):
        # Public parserSST method, adapted for attribute order and HLS links.
        headers=self.cm.getDefaultHeader();headers['Referer']=getattr(baseUrl,'meta',{}).get('Referer',str(baseUrl))
        ok,data=self.cm.getPage(baseUrl,{'header':headers})
        if not ok:return []
        page=self.cm.meta.get('url',str(baseUrl));host=urlparser.getDomain(page,False)
        meta={'User-Agent':headers['User-Agent'],'Referer':page,'Origin':host.rstrip('/')}
        links=[]
        for tag in re.findall(r'<source\b[^>]*>',data,re.I):
            source=ph.search(tag,r'''\bsrc\s*=\s*["']([^"']+)''')[0]
            label=ph.search(tag,r'''\b(?:label|res)\s*=\s*["']([^"']+)''')[0]
            if source:links.append((label or 'MP4',urljoin(page,source)))
        if not links:
            source=ph.search(data,r'''\bfile\s*:\s*["']([^"']+)''')[0]
            if '[' in source:
                links=re.findall(r'\[(\d+p)\](https?://[^\s,\]]+)',source)
            elif source:links=[('MP4',urljoin(page,source.replace(r'\/','/')))]
        result=[]
        for label,source in links:
            if not self.cm.isValidUrl(source):continue
            url=urlparser.decorateUrl(source,meta)
            if '.m3u8' in source:result.extend(getDirectM3U8Playlist(url))
            else:result.append({'name':label,'url':url})
        return result

    def parserVOESX(self, baseUrl):
            def voe_decode(ct, lut=None):
                txt = "".join(chr((ord(i) - 52) % 26 + 65) if 65 <= ord(i) <= 90 else chr((ord(i) - 84) % 26 + 97) if 97 <= ord(i) <= 122 else i for i in ct)
                if not lut:
                    lut = [re.escape(marker) for marker in ("#&", "%?", "*~", "~@", "^^", "!!", "@$")]
                for pattern in lut:
                    txt = re.sub(pattern, "_", txt)
                txt = "".join(txt.split("_"))

                def fix_b64_padding(s):
                    return s + "=" * (-len(s) % 4)

                try:
                    step1 = base64.b64decode(fix_b64_padding(txt)).decode()
                    step2 = "".join(chr(ord(c) - 3) for c in step1)
                    final = base64.b64decode(fix_b64_padding(step2[::-1])).decode()
                    return json_loads(final)
                except Exception as e:
                    printDBG(e)
                    return ""

            printDBG("parserVOESX baseUrl[%r]" % baseUrl)
            sts, data = self.cm.getPage(baseUrl, {'header': {'Referer': getattr(baseUrl, 'meta', {}).get('Referer', str(baseUrl))}})
            if not sts or not any(marker in data for marker in ("const currentUrl", "application/json", '";function', "hls")):
                # add 061026: VOE drops its rotation domains quickly (gone, or parked with a "Redirecting..." page);
                # the file id still plays via voe.sx
                fileId = ph.search(baseUrl, r"//[^/]+/(?:e/)?([0-9A-Za-z]+)")[0]
                if not fileId or "//voe.sx/" in baseUrl:
                    return False
                printDBG("parserVOESX %s gone or no VOE page -> voe.sx" % urlparser.getDomain(baseUrl))
                sts, data = self.cm.getPage("https://voe.sx/e/%s" % fileId)
                if not sts:
                    return False
            pageUrl = self.cm.meta.get("url", baseUrl)
            # fix 061026: the redirect page can lead to another redirect page (after ResolveURL voesx.py)
            for _hop in range(5):
                if "const currentUrl" not in data:
                    break
                nextUrl = ph.search(data, r"""window.location.href\s*=\s*['"]([^"^']+?)['"]""")[0]
                if not nextUrl:
                    break
                previousUrl = pageUrl
                pageUrl = urljoin(pageUrl, nextUrl)
                sts, data = self.cm.getPage(pageUrl, {"header": {"Referer": previousUrl}})
                if not sts:
                    return False
            if "<title>404" in data:
                SetIPTVPlayerLastHostError(_("The video has been removed."))
                return []
            # add 061026: the junk strings of the decoder change with VOE's player script, which lists them
            # (['@$','^^',...]); the built-in list stays the fallback
            lut = None
            script = ph.search(data, r"""json">\["[^"]+"]</script>\s*<script\s*src="([^"]+)""")[0]
            if script:
                stsS, dataS = self.cm.getPage(urljoin(pageUrl, script))
                table = ph.search(dataS, r"""(\[(?:'\W{2}'[,\]]){1,9})""")[0] if stsS else ""
                if table:
                    lut = [re.escape(x) for x in table[2:-2].split("','")]
                    printDBG("parserVOESX junk table from the player script: %s" % table)
            r = re.search(r"""['"]?hls['"]?\s*?:\s*?['"]([^'^"]+?)['"]""", data)
            if r:
                value = r.group(1)
                hlsUrl = value if value.startswith(("https://", "//")) else ensure_str(base64.b64decode(value + "=" * (-len(value) % 4)))
                if hlsUrl.startswith("//"):
                    hlsUrl = "https:" + hlsUrl
                if self.cm.isValidUrl(hlsUrl):
                    params = {"iptv_proto": "m3u8", "Referer": pageUrl, "Origin": urlparser.getDomain(pageUrl, False).rstrip("/")}
                    hlsUrl = urlparser.decorateUrl(hlsUrl, params)
                    return getDirectM3U8Playlist(hlsUrl, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999)
            else:
                r = re.search(r'\w+="([^"]+)";function', data)
                if not r:
                    r = re.search(r"""application/json">[^>]"([^"]+)""", data)
                urltab = []
                if r:
                    payload = ensure_str(r.group(1))
                    r = voe_decode(payload, lut)
                    if not r and lut:
                        r = voe_decode(payload)
                    if r:
                        subtitles = [{"title": "", "lang": x.get("label"), "url": urljoin(pageUrl, x.get("file"))} for x in r.get("captions", []) if x.get("kind") == "captions"]
                        key_list = ["source", "file", "direct_access_url"]
                        for key in key_list:
                            if key in r:
                                url = r[key]
                                if ".m3u8" in url:
                                    url = urlparser.decorateUrl(url, {"iptv_proto": "m3u8", "Referer": pageUrl, "Origin": urlparser.getDomain(pageUrl, False).rstrip("/"), "external_sub_tracks": subtitles})
                                    urltab.extend(getDirectM3U8Playlist(url, checkExt=False, checkContent=True, sortWithMaxBitrate=999999999))
                                else:
                                    if subtitles:
                                        url = urlparser.decorateUrl(url, {"external_sub_tracks": subtitles})
                                    urltab.append({"name": "MP4", "url": url})
                return urltab

    def parserMIXDROP(self, baseUrl):  # add 041026 - like ResolveURL mixdrop.py
            printDBG("parserMIXDROP baseUrl[%s]" % baseUrl)
            mediaId = re.search(r"/[fe]/(\w+)", baseUrl)
            if not mediaId:
                return []
            # ids are the same on every mixdrop domain; old ones are parked (.co, .vc, ...), mixdrop.ag redirects to the live one
            url = "https://mixdrop.ag/e/%s" % mediaId.group(1)
            HTTP_HEADER = self.cm.getDefaultHeader()
            HTTP_HEADER.update({"Referer": "https://mixdrop.ag/", "Origin": "https://mixdrop.ag"})
            urlParams = {"header": HTTP_HEADER}
            sts, data = self.cm.getPage(url, urlParams)
            if not sts:
                return []
            url = self.cm.meta.get("url", "") or url
            redirect = re.search(r"""location\s*=\s*["'](/[^'"]+)""", data)
            if redirect:
                url = urljoin(url, redirect.group(1))
                sts, data = self.cm.getPage(url, urlParams)
                if not sts:
                    return []
            if "(p,a,c,k,e,d)" in data:
                data = get_packed_data(data) or data
            src = re.search(r'(?:vsr|wurl|surl)[^=]*=\s*"([^"]+)', data)
            if not src:
                if re.search(r"can(?:'|&#0?39;)t find the (?:video|file)", data):
                    # download-only uploads (e.g. .ts recordings) and deleted files have no embed
                    SetIPTVPlayerLastHostError(_("MixDrop: this file is not available as a video stream (deleted or download only)."))
                return []
            src = src.group(1)
            if src.startswith("//"):
                src = "https:" + src
            return [{"name": "MP4", "url": urlparser.decorateUrl(src, {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": url})}]

