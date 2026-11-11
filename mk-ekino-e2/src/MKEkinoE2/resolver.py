#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Standalone Ekino/Byse resolver diagnostic for Python 3, without E2iPlayer.

The parserBYSE method below is retained from the PUBLIC e2iplayer-2026.10.18.05
archive, IPTVPlayer/libs/urlparser.py. Existing source comments and credits
are preserved. Standalone adapters: MK, 2026-10-22. GPL-3.0 text is embedded
at the end of this file. No private PE2I code or E2i account data is used.
Only public source discovery and manifest inspection are performed, not video
playback or downloads. Cookies and transient source URLs stay in memory.
"""
import argparse
import base64
from binascii import hexlify
import hashlib
from hashlib import sha256
import html as html_lib
import http.cookiejar
import ipaddress
import json
import os
from os import urandom
from pathlib import Path
from random import uniform
import re
import ssl
import tempfile
import time
import urllib.error
import urllib.parse
from urllib.parse import urlsplit as urlparse
import urllib.request
import xml.etree.ElementTree as ET

BASE = 'https://ekino.ws/'
TITLE = BASE + 'movie/show/ponad-prawem-hd-by-any-means-2026-lektor/43152'
MAX_PAGE = 2 * 1024 * 1024
DEFAULT_UA = ('Mozilla/5.0 (X11; Linux x86_64; rv:128.0) '
              'Gecko/20100101 Firefox/128.0')


class ResolveError(Exception):
    pass


class URL(str):
    def __new__(cls, value, meta=None):
        result = str.__new__(cls, value)
        result.meta = dict(meta if meta is not None else getattr(value, 'meta', {}))
        return result


class Body(str):
    pass


def b64urlEncode(value, strip=False):
    value = value.encode() if isinstance(value, str) else value
    out = base64.urlsafe_b64encode(value).decode('ascii')
    return out.rstrip('=') if strip else out


def json_dumps(value):
    return json.dumps(value, separators=(',', ':'))


def json_loads(value):
    return json.loads(value)


def printDBG(*args, **kwargs):
    # Original debug messages may contain temporary source URLs: discard them.
    pass


def _(value):
    return value


LAST_HOST_ERROR = False


def SetIPTVPlayerLastHostError(*args):
    global LAST_HOST_ERROR
    LAST_HOST_ERROR = True


class Notify:
    last = 0
    def setStatus(self, text):
        now = time.monotonic()
        if now - self.last > 5:
            self.last = now
            print(json.dumps({'stage': 'source_access_work',
                              'account_files_read': False}), flush=True)


NOTIFY = Notify()


def GetIPTVNotify():
    return NOTIFY


def checked_url(url):
    value = str(url)
    parsed = urllib.parse.urlsplit(value)
    host = (parsed.hostname or '').lower()
    if (parsed.scheme != 'https' or not host or parsed.username or parsed.password
            or parsed.port not in (None, 443) or '.' not in host
            or host.endswith(('.local', '.localhost', '.internal'))):
        raise ResolveError('unsupported_source_address')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ResolveError('source_address_not_public')
    return value


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Http:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
            urllib.request.HTTPCookieProcessor(self.jar), PublicRedirect())
        self.meta = {}
        self.steps = []

    @staticmethod
    def isValidUrl(value):
        try:
            checked_url(value)
            return True
        except (ResolveError,ValueError):
            return False

    def getDefaultHeader(self):
        return {'User-Agent': DEFAULT_UA, 'Accept-Encoding': 'identity', 'Accept': '*/*'}

    def getPage(self, url, params=None, post_data=None):
        params = params or {}
        headers = self.getDefaultHeader()
        headers.update(params.get('header', {}))
        payload = post_data.encode('utf-8') if isinstance(post_data, str) else post_data
        if isinstance(payload, dict):
            payload = urllib.parse.urlencode(payload).encode()
        request = urllib.request.Request(checked_url(url), data=payload, headers=headers)
        started = time.monotonic()
        try:
            response = self.opener.open(request, timeout=min(params.get('timeout', 25), 40))
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(MAX_PAGE + 1)
            if len(raw) > MAX_PAGE:
                raise ResolveError('source_response_too_large')
            body = Body(raw.decode('utf-8-sig', 'replace'))
            content_type = response.headers.get('Content-Type', '')
            self.meta = {'url': response.geturl(), 'status_code': response.code,
                         'content-type': content_type}
            body.meta = dict(self.meta)
            step = {'hostname': urllib.parse.urlsplit(response.geturl()).hostname,
                    'http_status': response.code, 'bytes_read': len(raw),
                    'request': 'POST' if payload is not None else 'GET',
                    'elapsed_ms': round((time.monotonic()-started)*1000)}
            # Endpoint categories, not video IDs, tokens, bodies or stream URLs.
            path = urllib.parse.urlsplit(str(url)).path
            for kind in ['captcha/verify', 'access/challenge', 'access/attest',
                         'playback', 'settings', 'details', 'captcha']:
                if path.endswith('/' + kind):
                    step['endpoint'] = kind
                    break
            if len(self.steps) < 40:
                self.steps.append(step)
            allowed = any(low <= response.code <= high
                          for low, high in params.get('ignore_http_code_ranges', []))
            return response.code == 200 or allowed, body


class urlparser:
    @staticmethod
    def getDomain(url, onlyDomain=True):
        parsed = urllib.parse.urlsplit(str(url))
        return parsed.netloc if onlyDomain else parsed.scheme + '://' + parsed.netloc + '/'

    @staticmethod
    def decorateUrl(url, meta):
        return URL(url, meta)


def attrs(line):
    return {k: quoted or unquoted for k, quoted, unquoted in re.findall(
        r'([A-Z0-9-]+)=(?:"([^"]*)"|([^,]*))(?:,|$)', line)}


def hls_options(client, url):
    # URL metadata also contains subtitle lists and playback options. Only
    # actual HTTP headers belong in the request; preserve the rest below.
    headers = {key: value for key, value in getattr(url, 'meta', {}).items()
               if key in ('User-Agent', 'Referer', 'Origin', 'Accept')
               and isinstance(value, str)}
    ok, body = client.getPage(url, {'header': headers})
    if not ok:
        raise ResolveError('manifest_http_error')
    if not body.lstrip().startswith('#EXTM3U'):
        raise ResolveError('manifest_not_hls')
    base=getattr(body,'meta',{}).get('url') or getattr(client,'meta',{}).get('url') or str(url)
    lines = body.splitlines()
    audio = {}
    for line in lines:
        if line.startswith('#EXT-X-MEDIA:'):
            item = attrs(line.split(':', 1)[1])
            if item.get('TYPE') == 'AUDIO':
                audio.setdefault(item.get('GROUP-ID', ''), []).append(item)
    result = []
    for i, line in enumerate(lines):
        if not line.startswith('#EXT-X-STREAM-INF:'):
            continue
        a = attrs(line.split(':', 1)[1])
        res = re.fullmatch(r'(\d+)x(\d+)', a.get('RESOLUTION', ''))
        resolution = (int(res[1]), int(res[2])) if res else (0, 0)
        bandwidth = int(a.get('BANDWIDTH', '0')) if a.get('BANDWIDTH', '0').isdigit() else 0
        video_uri = next((v.strip() for v in lines[i + 1:] if v.strip() and not v.startswith('#')), None)
        if not video_uri:
            continue
        renditions = audio.get(a.get('AUDIO', ''), []) or [{}]
        for track in renditions:
            language = track.get('LANGUAGE', '')
            if not re.fullmatch(r'[A-Za-z0-9_-]{0,16}', language):
                language = 'other'
            codec = a.get('CODECS', '')
            if not re.fullmatch(r'[A-Za-z0-9., _-]{0,120}', codec):
                codec = 'other'
            meta = dict(getattr(url, 'meta', {}))
            meta.update(language=language, iptv_proto='m3u8',video_url=urllib.parse.urljoin(base, video_uri),
                        audio_url=urllib.parse.urljoin(base, track['URI']) if track.get('URI') else '')
            result.append({'name': 'HLS', 'url': URL(base, meta),
                           'width': resolution[0], 'height': resolution[1],
                           'bitrate': bandwidth, 'language': language, 'codecs': codec})
    return result or [{'name': 'HLS', 'url': url, 'width': 0, 'height': 0,
                       'bitrate': 0, 'language': '', 'codecs': ''}]


ACTIVE_HTTP = None


def getDirectM3U8Playlist(url, sortWithMaxBitrate=99999999, **kwargs):
    return hls_options(ACTIVE_HTTP, url)


class python_aesgcm:
    @staticmethod
    def new(key):
        from Crypto.Cipher import AES
        class Cipher:
            def open(self, iv, payload):
                if len(payload) < 16:
                    raise ResolveError('invalid_playback_payload')
                return AES.new(key, AES.MODE_GCM, nonce=iv).decrypt_and_verify(payload[:-16], payload[-16:])
        return Cipher()


ECDSA_NIST256p = None


class ECDSA_SigningKey:
    @staticmethod
    def generate(curve=None, hashfunc=None):
        from Crypto.PublicKey import ECC
        from Crypto.Signature import DSS
        from Crypto.Hash import SHA256
        key = ECC.generate(curve='P-256')
        class Verifying:
            def to_string(self):
                return int(key.pointQ.x).to_bytes(32, 'big') + int(key.pointQ.y).to_bytes(32, 'big')
        class Signing:
            verifying_key = Verifying()
            def sign(self, value, hashfunc=None):
                return DSS.new(key, 'fips-186-3', encoding='binary').sign(SHA256.new(value))
        return Signing()


class Byse:
    BYSE_ACCESS = {}
    def __init__(self, client):
        self.cm = client
        from fast_pow import make_solver
        self.pow_solver = make_solver()
        self.pow_stats = {}

    def parserBYSE(self, baseUrl):  # fix 240826 - captcha/proof-of-work challenge support
            UA = "Mozilla/5.0 (Linux; Android 10; TX6s) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"

            def fp(x, y, z):  # thx Gujal00
                v_id = hexlify(urandom(x)).decode()
                d_id = hexlify(urandom(x)).decode()
                ctime = int(time.time())
                t_data = {"viewer_id": v_id, "device_id": d_id, "confidence": round(uniform(y, z), 2), "iat": ctime, "exp": ctime + 600}
                t_bdata = b64urlEncode(json_dumps(t_data), strip=True)
                t_sig = b64urlEncode(sha256(t_bdata.encode()).digest(), strip=True)
                token = "{0}.{1}".format(t_bdata, t_sig)
                t_data.update({"token": token})
                t_data.pop("iat")
                t_data.pop("exp")
                return {"fingerprint": t_data}

            def ft(e):
                t = e.replace("-", "+").replace("_", "/")
                r = 0 if len(t) % 4 == 0 else 4 - len(t) % 4
                n = t + "=" * r
                return base64.b64decode(n)

            def xn(e, v):
                if v:
                    v = int(v)
                    if 0 < v <= len(e):
                        e = [e[v - 1], e[len(e) - v]]
                t = list(map(ft, e))
                return b"".join(t)

            def fh(v):
                return b64urlEncode(sha256(str(v).encode("ascii")).digest(), strip=True)

            def wn(challenge):
                sk = ECDSA_SigningKey.generate(curve=ECDSA_NIST256p, hashfunc=sha256)
                vk = sk.verifying_key.to_string()
                nonce = str(challenge.get("nonce") or "")
                signature = sk.sign(nonce.encode(), hashfunc=sha256)
                pub = {"crv": "P-256", "ext": True, "key_ops": ["verify"], "kty": "EC", "x": b64urlEncode(vk[:32], strip=True), "y": b64urlEncode(vk[32:], strip=True)}
                r = uniform(0, 1)
                return {
                    "viewer_id": "", "device_id": "", "challenge_id": challenge.get("challenge_id", ""), "nonce": nonce,
                    "signature": b64urlEncode(signature, strip=True), "public_key": pub,
                    "client": {
                        "user_agent": UA, "architecture": "arm", "bitness": "32", "platform": "Android", "platform_version": "10.0.0",
                        "model": "TX6s", "ua_full_version": "137.0.7337.0",
                        "brand_full_versions": [{"brand": "Chromium", "version": "137.0.7337.0"}],
                        "pixel_ratio": 1, "screen_width": 1280, "screen_height": 720, "color_depth": 24,
                        "languages": ["en-US"], "timezone": "America/New_York", "hardware_concurrency": 4, "device_memory": 2,
                        "touch_points": 1, "webgl_vendor": "Google Inc. (ARM)", "webgl_renderer": "ANGLE (ARM, Mali-G31 MP2, OpenGL ES 3.2)",
                        "canvas_hash": fh(r), "audio_hash": fh(r + 1), "webgl_params_hash": fh(r + 2), "fonts_hash": fh(r + 3), "codecs_hash": fh(r + 4),
                        "media_devices": "ai1ao1vi4", "pointer_type": "coarse",
                        "extra": {"vendor": "Google Inc.", "appVersion": UA[len("Mozilla/"):]},
                    },
                    "storage": {}, "attributes": {"entropy": "high"},
                }

            # Proof of work of the player (assets/pow-*.js: gr/wr/Er): find a counter s so that the custom
            # 512-word ChaCha-style hash of "<pow_nonce>:<s>" starts with pow_difficulty zero bits. Pure Python
            # is ~100x slower than the browser, so the solver is written flat: the ChaCha quarter round (ye) is
            # inlined on local variables (no function calls or list writes per round), the constant
            # "<pow_nonce>:" prefix is absorbed only once, and gr() stops at the first non-zero output word.
            def powBytes(s):
                # like the player's yr(): one byte per char code (& 255); a list behaves the same on py2 and py3
                return [ord(ch) & 255 for ch in s]

            def grAbsorb(data, state=(1779033703, 3144134277, 1013904242, 2773480762)):
                M = 0xFFFFFFFF
                a, b, c, d = state
                for i in data:
                    a = (a + i) & M
                    a = ((a << 7) | (a >> 25)) & M
                    a = (a + b) & M
                    d ^= a
                    d = ((d << 16) | (d >> 16)) & M
                    c = (c + d) & M
                    b ^= c
                    b = ((b << 12) | (b >> 20)) & M
                    a = (a + b) & M
                    d ^= a
                    d = ((d << 8) | (d >> 24)) & M
                    c = (c + d) & M
                    b ^= c
                    b = ((b << 7) | (b >> 25)) & M
                return a, b, c, d

            def gr(state, tail):
                # number of leading zero bits of the player's gr() hash of (absorbed prefix + tail), same as
                # wr(gr()) in the player JS; the eight output words are only computed until one is non-zero
                M = 0xFFFFFFFF
                a, b, c, d = grAbsorb(tail, state)
                for _i in range(8):
                    a = (a + b) & M
                    d ^= a
                    d = ((d << 16) | (d >> 16)) & M
                    c = (c + d) & M
                    b ^= c
                    b = ((b << 12) | (b >> 20)) & M
                    a = (a + b) & M
                    d ^= a
                    d = ((d << 8) | (d >> 24)) & M
                    c = (c + d) & M
                    b ^= c
                    b = ((b << 7) | (b >> 25)) & M
                r = [0] * 512
                for i in range(512):
                    a = (a + b) & M
                    d ^= a
                    d = ((d << 16) | (d >> 16)) & M
                    c = (c + d) & M
                    b ^= c
                    b = ((b << 12) | (b >> 20)) & M
                    a = (a + b) & M
                    d ^= a
                    d = ((d << 8) | (d >> 24)) & M
                    c = (c + d) & M
                    b ^= c
                    b = ((b << 7) | (b >> 25)) & M
                    r[i] = a ^ c
                for _i in range(2):
                    for s in range(512):
                        x = r[s]
                        x = (x + r[x & 511]) & M
                        x = ((x << 13) | (x >> 19)) & M
                        x ^= (r[(s + 1) & 511] * 2654435761) & M
                        r[s] = x
                        a ^= x
                        a = (a + b) & M
                        d ^= a
                        d = ((d << 16) | (d >> 16)) & M
                        c = (c + d) & M
                        b ^= c
                        b = ((b << 12) | (b >> 20)) & M
                        a = (a + b) & M
                        d ^= a
                        d = ((d << 8) | (d >> 24)) & M
                        c = (c + d) & M
                        b ^= c
                        b = ((b << 7) | (b >> 25)) & M
                zeros = 0
                for i in range(0, 512, 64):
                    a = (a + b) & M
                    d ^= a
                    d = ((d << 16) | (d >> 16)) & M
                    c = (c + d) & M
                    b ^= c
                    b = ((b << 12) | (b >> 20)) & M
                    a = (a + b) & M
                    d ^= a
                    d = ((d << 8) | (d >> 24)) & M
                    c = (c + d) & M
                    b ^= c
                    b = ((b << 7) | (b >> 25)) & M
                    s = a
                    for x in r[i:i + 64]:
                        s = (s + x) & M
                        s = ((s << 5) | (s >> 27)) & M
                        s ^= (x * 2246822519) & M
                    s ^= c
                    if s:
                        return zeros + 32 - s.bit_length()
                    zeros += 32
                return zeros

            def er(t, e, timeout, progress=None):
                # returns (solution or None, hashes tried); the time limit is checked every 16 hashes
                # (a few seconds at most even on a slow ARM box); progress(seconds) about once a second
                if e <= 0:
                    return "0", 0
                state = grAbsorb(powBytes(t + ":"))
                start = shown = time.time()
                s = 0
                while True:
                    for _i in range(16):
                        if gr(state, powBytes(str(s))) >= e:
                            return str(s), s + 1
                        s += 1
                    now = time.time()
                    if now - start > timeout:
                        return None, s
                    if progress and now - shown >= 1.0:
                        shown = now
                        progress(int(now - start))

            def powProgress(seconds):
                # add 101026: the loading line tells why the start takes so long (up to a few minutes on a box);
                # a framework without the status line (zadmario) just waits
                notify = GetIPTVNotify()
                if hasattr(notify, "setStatus"):
                    notify.setStatus("%s\n%s" % (_("Loading"), _("%s: decrypting the stream, this can take a while (%d s)") % ("Byse", seconds)))

            def statusCode(data, sts):
                try:
                    code = getattr(data, "meta", {}).get("status_code")
                    if code:
                        return code
                except Exception:
                    pass
                return 200 if sts else 0

            def tryJson(data):
                try:
                    return json_loads(data)
                except Exception:
                    return None

            def jsonPost():
                # params for the API POST endpoints (challenge/attest/captcha/
                # verify/playback). Send a real JSON Content-Type (pycurl otherwise
                # defaults to application/x-www-form-urlencoded) and disable the
                # automatic "Expect: 100-continue" handshake, matching the site's
                # own frontend and upstream ResolveURL (jdata=True).
                hdr = dict(HTTP_HEADER)
                hdr["Content-Type"] = "application/json"
                hdr["Expect"] = ""
                return {"header": hdr, "raw_post_data": True, "timeout": 40}

            # embedding site of a domain-locked video (e.g. serijebalkan.com): its Referer comes in the link meta
            parent = getattr(baseUrl, "meta", {}).get("Referer", "")
            baseUrl = baseUrl.replace("/d/", "/e/")
            printDBG("parserBYSE baseUrl[%s]" % baseUrl)
            urltab = []
            for redirectDomain in ["boosteradx.online", "byse.sx", "streamlyplayer.online"]:
                baseUrl = baseUrl.replace(redirectDomain, "streamlyplayero.online")
            ref = urlparser.getDomain(baseUrl, False)
            if "streamlyplayero.online" in ref:
                # fix 101026: streamlyplayero.online only frames the player of the current byse domain (bysekoze.com),
                # its api answers with that html page - follow the frame
                sts, page = self.cm.getPage(baseUrl, {"header": {"User-Agent": UA, "Referer": parent or ref}})
                frame = re.search(r"""<iframe[^>]+src=["'](https?://[^/"']+/)(?:e|d)/""", page) if sts else None
                if frame and frame.group(1) != ref:
                    baseUrl = baseUrl.replace(ref, frame.group(1), 1)
                    ref = frame.group(1)
            midMatch = re.search(r"/(?:e|d|download)/([0-9a-zA-Z]+)", baseUrl)
            if not midMatch:
                return []
            mid = midMatch.group(1)
            HTTP_HEADER = self.cm.getDefaultHeader()
            HTTP_HEADER["User-Agent"] = UA
            HTTP_HEADER["Referer"] = ref
            HTTP_HEADER["Origin"] = ref[:-1]

            embed = ""
            detailsUrl = "%sapi/videos/%s/details" % (ref, mid)
            # with_metadata=True is required for statusCode() below to see the
            # real HTTP status: getPageWithPyCurl() treats a 404 as sts=True by
            # default (ignore_http_code_ranges), and only attaches .meta when
            # asked to - without it, statusCode() always fell through to its
            # sts-based 200/0 guess and this 404 retry never actually fired,
            # even though the site returns a valid JSON body on 404s.
            sts, data = self.cm.getPage(detailsUrl, {"header": dict(HTTP_HEADER), "with_metadata": True})
            details = tryJson(data) if sts else None
            if details is None or statusCode(data, sts) == 404:
                embed = "embed/"
                detailsUrl = "%sapi/videos/%s/%sdetails" % (ref, mid, embed)
                hdr = dict(HTTP_HEADER)
                if parent:  # add 041026: domain-locked videos check Referer/Origin of the embedding site
                    hdr["Referer"] = urlparser.getDomain(parent, False)
                    hdr["Origin"] = hdr["Referer"][:-1]
                # 404 {"error": "video record missing: video not found"}, 403 {"error": "embedding from this domain is not allowed ..."}
                sts, data = self.cm.getPage(detailsUrl, {"header": hdr, "ignore_http_code_ranges": [(403, 404)]})
                if not sts:
                    return []
                details = tryJson(data)
                if not isinstance(details, dict):
                    return []
                if details.get("error") and not details.get("embed_frame_url"):
                    printDBG("parserBYSE details error [%s]" % details["error"])
                    SetIPTVPlayerLastHostError(_("The video has been removed.") if "not found" in details["error"] else _("Content not available"))
                    return []

            embedUrl = details.get("embed_frame_url")
            if embedUrl:
                ref = urlparser.getDomain(embedUrl, False)
                HTTP_HEADER["X-Embed-Parent"] = baseUrl
                HTTP_HEADER["Referer"] = ref
                HTTP_HEADER["Origin"] = ref[:-1]
                if parent:  # the player sends the embedding site as embedParentHost / Referrer
                    HTTP_HEADER["X-Embed-Origin"] = urlparser.getDomain(parent).replace("www.", "", 1)
                    HTTP_HEADER["X-Embed-Referer"] = urlparser.getDomain(parent, False)

            settingsUrl = "%sapi/videos/%s/%ssettings" % (ref, mid, embed)
            sts, data = self.cm.getPage(settingsUrl, {"header": dict(HTTP_HEADER)})
            settings = tryJson(data) if sts else None
            if settings is None:
                settings = {}

            playbackUrl = "%sapi/videos/%s/%splayback" % (ref, mid, embed)
            needCaptcha = settings.get("captcha_required")
            if not needCaptcha:
                # fix 071026: when the settings call fails (settings = {}) the plain playback answers
                # HTTP 428 {"error":"captcha_required"}: fall back to the captcha flow instead of returning nothing
                params = jsonPost()
                params["ignore_http_code_ranges"] = [(428, 428)]
                sts, data = self.cm.getPage(playbackUrl, params, json_dumps(fp(16, 0.83, 0.94)))
                if sts and (tryJson(data) or {}).get("error") == "captcha_required":
                    printDBG("parserBYSE playback needs a captcha although settings said no")
                    needCaptcha = True
            if needCaptcha:
                # a solved captcha stays valid for the player domain for a while (verify expires_in, 1800 s):
                # reuse it for the next video instead of solving the proof of work again (minutes on a slow box)
                sts = False
                access = self.BYSE_ACCESS.get(ref)
                if access and access[0] > time.time():
                    HTTP_HEADER["X-Captcha-Token"] = access[2]
                    sts, data = self.cm.getPage(playbackUrl, jsonPost(), json_dumps({"fingerprint": access[1]}))
                    printDBG("parserBYSE reused captcha token: %s" % sts)
                    if not sts or not isinstance(tryJson(data), dict) or (tryJson(data) or {}).get("error"):
                        sts = False
                        self.BYSE_ACCESS.pop(ref, None)
                        HTTP_HEADER.pop("X-Captcha-Token", None)
                if not sts:
                    challengeUrl = "%sapi/videos/access/challenge" % ref
                    sts, data = self.cm.getPage(challengeUrl, jsonPost(), "")
                    challenge = tryJson(data) if sts else None
                    if challenge is None:
                        return []

                    attestUrl = "%sapi/videos/access/attest" % ref
                    sts, data = self.cm.getPage(attestUrl, jsonPost(), json_dumps(wn(challenge)))
                    attest = tryJson(data) if sts else None
                    if not attest or not attest.get("token"):  # fix 071026: fingerprint rejected - tell the user
                        printDBG("parserBYSE attest failed [%s]" % data)
                        SetIPTVPlayerLastHostError(_("%s could not solve the captcha.") % "Byse")
                        return []
                    fingerprint = {"token": attest.get("token"), "viewer_id": attest.get("viewer_id"), "device_id": attest.get("device_id"), "confidence": attest.get("confidence")}

                    captchaUrl = "%sapi/videos/%s/%scaptcha" % (ref, mid, embed)
                    sts, data = self.cm.getPage(captchaUrl, jsonPost(), json_dumps({"fingerprint": fingerprint}))
                    captcha = tryJson(data) if sts else None
                    if not captcha or not captcha.get("pow_token"):  # fix 071026
                        printDBG("parserBYSE captcha request failed [%s]" % data)
                        SetIPTVPlayerLastHostError(_("%s could not solve the captcha.") % "Byse")
                        return []
                    # mobile fingerprints get difficulty 12 (~4096 hashes, ~1 min on an ARM box), desktop ones 16;
                    # the pow_token is valid for expires_in (1800 s), so the box may take longer than the
                    # browser's 20 s
                    difficulty = int(captcha.get("pow_difficulty") or 0)
                    timeLimit = min(180.0, max(20.0, float(captcha.get("expires_in") or 300) - 60.0))
                    powStart = time.time()
                    powProgress(0)
                    solver = self.pow_solver or er
                    solution, hashes = solver(captcha.get("pow_nonce") or "", difficulty, timeLimit, powProgress)
                    self.pow_stats = {"engine": "native_armv7" if self.pow_solver else "python", "difficulty": difficulty,
                                      "hashes": hashes, "elapsed_ms": round((time.time()-powStart)*1000)}
                    printDBG("parserBYSE proof of work difficulty %d: %s after %d hashes in %.1fs" % (difficulty, solution, hashes, time.time() - powStart))
                    if solution is None:
                        SetIPTVPlayerLastHostError(_("%s could not solve the captcha.") % "Byse")
                        return []

                    verifyUrl = "%sapi/videos/%s/%scaptcha/verify" % (ref, mid, embed)
                    verifyPost = {"pow_token": captcha.get("pow_token"), "solution": solution, "fingerprint": fingerprint}
                    sts, data = self.cm.getPage(verifyUrl, jsonPost(), json_dumps(verifyPost))
                    verify = tryJson(data) if sts else None
                    if not verify or not verify.get("token"):
                        printDBG("parserBYSE captcha verify failed [%s]" % data)
                        SetIPTVPlayerLastHostError(_("%s could not solve the captcha.") % "Byse")
                        return []
                    HTTP_HEADER["X-Captcha-Token"] = verify["token"]
                    lifetime = min(float(verify.get("expires_in") or 0), 1800.0) - 60.0
                    if lifetime > 0:
                        self.BYSE_ACCESS[ref] = (time.time() + lifetime, fingerprint, verify["token"])

                    sts, data = self.cm.getPage(playbackUrl, jsonPost(), json_dumps({"fingerprint": fingerprint}))
            if not sts:
                return []

            html = tryJson(data)
            if html is None:
                return []
            if html.get("error") and not html.get("sources") and not html.get("playback"):  # fix 071026: surface API errors
                printDBG("parserBYSE playback error [%s]" % html["error"])
                SetIPTVPlayerLastHostError(_("%s could not solve the captcha.") % "Byse" if "captcha" in html["error"] else _("Content not available"))
                return []
            sources = html.get("sources")
            if not sources:
                pd = html.get("playback")
                if pd:
                    iv = ft(pd.get("iv"))
                    key = xn(pd.get("key_parts"), pd.get("version"))
                    pl = ft(pd.get("payload"))
                    cipher = python_aesgcm.new(key)
                    ct = cipher.open(iv, pl)
                    html = json_loads(ct.decode("latin-1"))
                    sources = html.get("sources")
            if sources:
                seen = set()
                for x in sources:
                    if not x.get("url") or x["url"] in seen:
                        continue  # fix 101026: the playback data names the same master playlist up to three times
                    seen.add(x["url"])
                    url = urlparser.decorateUrl(x.get("url"), {"User-Agent": HTTP_HEADER["User-Agent"], "Referer": ref, "Origin": ref[:-1]})
                    if ".m3u8" in url:
                        urltab.extend(getDirectM3U8Playlist(url, sortWithMaxBitrate=99999999))
                    else:
                        urltab.append({"name": x.get("label", ""), "url": url})
            return urltab

