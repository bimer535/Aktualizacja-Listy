"""Authenticated VOD playback adapter; credentials and licence data stay in memory.

HAPI playset/view protocol follows the public GPL CANAL+ VOD integration.
The service decides availability. No purchase or subscription changes are made.
"""
import base64
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import canal_stream_test_v2 as stream

HAPI = 'https://secure-gen-hapi.canal-plus.com'
MAX_BODY = 4 * 1024 * 1024


def api_url(value):
    if not isinstance(value, str):
        raise stream.StreamError('vod_invalid_api_reference')
    value = urllib.parse.urljoin(HAPI + '/', value)
    p = urllib.parse.urlsplit(value)
    if (p.scheme != 'https' or p.hostname != 'secure-gen-hapi.canal-plus.com'
            or p.port not in (None, 443) or p.username or p.password or p.fragment):
        raise stream.StreamError('vod_invalid_api_reference')
    return value


class SameApiRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        api_url(urllib.parse.urljoin(req.full_url, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class VodApi:
    def __init__(self, authentication, device_id, opener=None):
        token = authentication.get('passToken')
        if not isinstance(token, str) or not token or not re.fullmatch(r'[a-zA-Z0-9-]{8,80}', str(device_id)):
            raise stream.StreamError('authenticated_session_missing')
        self.headers = {
            'User-Agent': 'Mozilla/5.0 MK-Canal-E2', 'Accept': 'application/json,application/xml,*/*',
            'Accept-Language': 'pl-PL,pl;q=0.9', 'Accept-Encoding': 'identity',
            'Origin': 'https://www.canalplus.com', 'XX-DOMAIN': 'cppol', 'XX-OZ': 'cppol',
            'XX-OL': 'pl', 'XX-SERVICE': 'mycanal', 'XX-OPERATOR': 'pc',
            'XX-API-VERSION': '3.0', 'XX-SPYRO-VERSION': '3.0',
            'XX-Profile-Id': '0', 'XX-DEVICE': 'pc ' + str(device_id),
            'Authorization': 'PASS Token="%s"' % urllib.parse.quote(token, safe='')}
        self.opener = opener or urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl.create_default_context()), SameApiRedirect())
        self.stage = 'vod_playset'

    def request(self, url, payload=None, method='GET', binary=False):
        headers = dict(self.headers)
        body = payload
        if isinstance(payload, dict):
            body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        elif isinstance(payload, bytes):
            headers['Content-Type'] = 'text/plain'
        req = urllib.request.Request(api_url(url), data=body, method=method, headers=headers)
        try:
            with self.opener.open(req, timeout=25) as response:
                raw = response.read(MAX_BODY + 1)
        except urllib.error.HTTPError as e:
            raise stream.StreamError('vod_service_http_error', http_status=e.code) from None
        except (urllib.error.URLError, OSError):
            raise stream.StreamError('vod_service_connection_error') from None
        if len(raw) > MAX_BODY:
            raise stream.StreamError('vod_service_response_too_large')
        if binary:
            return raw
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError):
            raise stream.StreamError('vod_service_invalid_response') from None

    def playset(self, cid):
        if not re.fullmatch(r'[0-9]{1,15}(?:_[0-9]{1,10})?', str(cid)):
            raise stream.StreamError('vod_invalid_content_id')
        self.stage = 'vod_playset'
        result = self.request('/conso/playset/unit/' + str(cid))
        if not isinstance(result, dict):
            raise stream.StreamError('vod_service_invalid_response')
        return result

    def resolve(self, cid):
        data = self.playset(cid)
        available = data.get('available')
        if not isinstance(available, list) or not available:
            raise stream.StreamError('vod_not_available_for_account')
        options = [v for v in available if isinstance(v, dict)
                   and 'DRM_COMMON_ENCRYPTION' in str(v.get('drmType', ''))]
        if not options:
            raise stream.StreamError('vod_supported_drm_not_available')
        def score(option):
            quality = str(option.get('quality', '')).upper()
            return (0 if 'DASH' in str(option.get('distTechnology', '')).upper() else 1,
                    0 if quality in ('HD', 'HD1080', 'FULLHD', '1080') else 1 if 'HD' in quality else 2)
        fields = ('comMode', 'contentId', 'distMode', 'distTechnology', 'drmType',
                  'functionalType', 'hash', 'idKey', 'quality')
        option = sorted(options, key=score)[0]
        if any(k not in option for k in fields):
            raise stream.StreamError('vod_playset_format_changed')
        payload = {key: option[key] for key in fields}
        payload['contentType'] = option['distMode']
        self.stage = 'vod_view'
        view = self.request('/conso/view', payload, 'PUT')
        if not isinstance(view, dict) or not view.get('@medias') or not view.get('@licence'):
            raise stream.StreamError('vod_view_not_granted')
        media_url, licence = api_url(view['@medias']), api_url(view['@licence'])
        self.stage = 'vod_medias'
        medias = self.request(media_url)
        candidates = manifest_candidates(medias)
        if not candidates:
            raise stream.StreamError('vod_dash_manifest_missing')
        self.stage = 'vod_manifest'
        last_error = None
        for manifest in candidates[:4]:
            try:
                root, final_url = stream.resolve_mpd(stream.Http(), manifest)
                if sum(1 for node in root if node.tag.rsplit('}', 1)[-1] == 'Period') != 1:
                    raise stream.StreamError('vod_multiple_periods_not_supported')
                return root, final_url, licence
            except stream.StreamError as error:
                if error.reason == 'vod_multiple_periods_not_supported':
                    raise
                last_error = error
        raise stream.StreamError('vod_dash_manifest_unavailable',
                                 http_status=getattr(last_error, 'details', {}).get('http_status', 0))

    def licence(self, url, challenge):
        self.stage = 'vod_licence'
        p = urllib.parse.urlsplit(api_url(url))
        query = dict(urllib.parse.parse_qsl(p.query))
        query['drmType'] = 'DRM_WIDEVINE'
        target = urllib.parse.urlunsplit(p._replace(query=urllib.parse.urlencode(query)))
        # HAPI expects a base64 challenge in text/plain and may wrap its response
        # in XML (contentid) rather than return a raw Widevine protobuf.
        raw = self.request(target, base64.b64encode(challenge), 'POST', binary=True)
        return decode_licence(raw)


def manifest_candidates(medias):
    candidates = []
    def walk(node, depth=0):
        if depth > 8:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ('distribURL', 'manifestUrl', 'manifestURL', 'url', 'src') and isinstance(v, str):
                    try:
                        url = stream.checked_url(v)
                    except stream.StreamError:
                        continue
                    path = urllib.parse.urlsplit(url).path.lower()
                    if '.mpd' in path:
                        candidates.insert(0, url)
                    elif path.endswith('.ism') or path.endswith('.isml'):
                        candidates.append(url.rstrip('/') + '/manifest(format=mpd-time-csf)')
                elif isinstance(v, (dict, list)):
                    walk(v, depth + 1)
        elif isinstance(node, list):
            for v in node[:100]:
                walk(v, depth + 1)
    walk(medias)
    return list(dict.fromkeys(candidates))


def decode_licence(raw):
    if not raw:
        raise stream.StreamError('vod_empty_licence')
    stripped = raw.lstrip()
    if stripped.startswith(b'<'):
        try:
            root = ET.fromstring(raw)
            for node in root.iter():
                if any(k.lower() == 'contentid' for k in node.attrib) and node.text:
                    return base64.b64decode(''.join(node.text.split()), validate=True)
        except (ET.ParseError, ValueError):
            pass
        raise stream.StreamError('vod_licence_not_granted')
    if stripped.startswith((b'{', b'[')):
        try:
            data = json.loads(raw)
            for key in ('license', 'licence', 'licenseData', 'LicenceData'):
                if isinstance(data, dict) and isinstance(data.get(key), str):
                    return base64.b64decode(''.join(data[key].split()), validate=True)
        except (ValueError, UnicodeError):
            pass
        raise stream.StreamError('vod_licence_not_granted')
    # Raw protobuf from the license service is passed directly to the CDM.
    return raw
