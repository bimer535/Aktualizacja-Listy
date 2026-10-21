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
from vod_data import CATALOGUE_USER_AGENT
from vod_http_diagnostics import error_shape

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
    def __init__(self, authentication, device_id, opener=None, media_http=None):
        token = authentication.get('passToken')
        if not isinstance(token, str) or not token or not re.fullmatch(r'[a-zA-Z0-9-]{8,80}', str(device_id)):
            raise stream.StreamError('authenticated_session_missing')
        self.headers = {
            'User-Agent': CATALOGUE_USER_AGENT, 'Accept': 'application/json,application/xml,*/*',
            'Accept-Language': 'pl-PL,pl;q=0.9', 'Accept-Encoding': 'identity',
            'Origin': 'https://www.canalplus.com', 'XX-DOMAIN': 'cppol', 'XX-OZ': 'cppol',
            'XX-OL': 'pl', 'XX-SERVICE': 'mycanal', 'XX-OPERATOR': 'pc',
            'XX-API-VERSION': '3.0', 'XX-SPYRO-VERSION': '3.0',
            'XX-Profile-Id': '0', 'XX-DEVICE': 'pc ' + str(device_id),
            'Authorization': 'PASS Token="%s"' % urllib.parse.quote(token, safe='')}
        self.opener = opener or urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl.create_default_context()), SameApiRedirect())
        self.stage = 'vod_playset'
        self.diagnostic = {}
        self.media_http = media_http if media_http is not None else stream.Http(user_agent=CATALOGUE_USER_AGENT)

    def request(self, url, payload=None, method='GET', binary=False):
        self.diagnostic = {}
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
            status = e.code
            # Playset metadata only. Never inspect or include licence bodies.
            if self.stage == 'vod_playset':
                try:
                    raw = e.read(65536)
                    self.diagnostic = dict(error_shape(raw), http_status=status,
                                           user_agent_profile='standard_browser')
                except (OSError, ValueError):
                    self.diagnostic = {'http_status': status, 'response_read_failed': True}
            e.close()
            raise stream.StreamError('vod_service_http_error', http_status=status) from None
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
                   and any(kind in str(v.get('drmType', '')).upper()
                           for kind in ('COMMON_ENCRYPTION', 'WIDEVINE'))]
        if not options:
            raise stream.StreamError('vod_supported_drm_not_available')
        def score(option):
            quality = str(option.get('quality', '')).upper()
            return (0 if 'DASH' in str(option.get('distTechnology', '')).upper() else 1,
                    0 if 'WIDEVINE' in str(option.get('drmType', '')).upper() else 1,
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
        attempts = []
        self.diagnostic = {'manifest_candidate_count': len(candidates),
                           'user_agent_profile': 'standard_browser',
                           'available_formats': available_format_summary(available),
                           'supported_option_count': len(options),
                           'selected_drm_profile': drm_profile(option),
                           'selected_delivery_is_dash': 'DASH' in str(option.get('distTechnology', '')).upper(),
                           'manifest_attempts': attempts}
        last_error = None
        for manifest in candidates[:4]:
            parts = urllib.parse.urlsplit(manifest)
            attempt = {'candidate_type': 'packager_dash' if 'format=mpd-' in parts.path.casefold() else 'provided_dash',
                       'has_query_parameters': bool(parts.query)}
            attempts.append(attempt)
            try:
                root, final_url = stream.resolve_mpd(self.media_http, manifest)
                if sum(1 for node in root if node.tag.rsplit('}', 1)[-1] == 'Period') != 1:
                    raise stream.StreamError('vod_multiple_periods_not_supported')
                attempt['result'] = 'mpd_loaded'
                attempt.update(manifest_response_metadata(self.media_http))
                return root, final_url, licence
            except stream.StreamError as error:
                known = {'http_error', 'connection_or_tls_error', 'smooth_streaming_received_instead_of_dash',
                         'hls_received_instead_of_dash', 'unrecognized_stream_response', 'invalid_stream_descriptor',
                         'descriptor_has_no_supported_url', 'vod_multiple_periods_not_supported'}
                attempt['result'] = error.reason if error.reason in known else 'manifest_resolution_failed'
                attempt.update(manifest_response_metadata(self.media_http))
                code = error.details.get('http_status')
                if isinstance(code, int): attempt['http_status'] = code
                if error.reason == 'vod_multiple_periods_not_supported':
                    raise
                last_error = error
        # A Smooth source is a different transport. Inspect it once for a clear
        # diagnosis after DASH failed; do not claim that the DASH-only player
        # can play it or copy private E2iPlayer flags into the native command.
        sources = smooth_candidates(medias)
        if sources:
            check = inspect_source_manifest(self.media_http, sources[0])
            self.diagnostic['source_manifest_check'] = check
            if check.get('result') == 'smooth_streaming':
                raise stream.StreamError('vod_smooth_streaming_not_supported')
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
    direct, derived = [], []
    def walk(node, depth=0):
        if depth > 8:
            return
        if isinstance(node, dict):
            mime = str(node.get('mimeType', node.get('mime_type', ''))).split(';', 1)[0].strip().lower()
            for k, v in node.items():
                if k in ('distribURL', 'manifestUrl', 'manifestURL', 'url', 'src') and isinstance(v, str):
                    try:
                        url = stream.checked_url(v)
                    except stream.StreamError:
                        continue
                    parts = urllib.parse.urlsplit(url)
                    path = parts.path.rstrip('/')
                    if mime == 'application/dash+xml' or '.mpd' in path.casefold() or 'format=mpd-' in path.casefold():
                        direct.append(url)
                    elif path.casefold().endswith(('.ism', '.isml')):
                        # Change the path only. Appending to a complete signed URL
                        # would put the manifest suffix INSIDE its query token.
                        derived.append(urllib.parse.urlunsplit(parts._replace(
                            path=path + '/manifest(format=mpd-time-csf)')))
                    elif re.search(r'\.(?:ism|isml)/manifest$', path, re.IGNORECASE):
                        derived.append(urllib.parse.urlunsplit(parts._replace(
                            path=path + '(format=mpd-time-csf)')))
                elif isinstance(v, (dict, list)):
                    walk(v, depth + 1)
        elif isinstance(node, list):
            for v in node[:100]:
                walk(v, depth + 1)
    walk(medias)
    return list(dict.fromkeys(direct + derived))


def drm_profile(option):
    value = str(option.get('drmType', '')).upper()
    if 'WIDEVINE' in value:
        return 'widevine'
    if 'COMMON_ENCRYPTION' in value:
        return 'common_encryption'
    if 'PLAYREADY' in value:
        return 'playready'
    return 'other'


def available_format_summary(available):
    """Fixed labels and counts only; never export offer ids, hashes or tokens."""
    counts = {}
    for option in available:
        if not isinstance(option, dict):
            continue
        delivery = str(option.get('distTechnology', '')).upper()
        delivery = 'dash' if 'DASH' in delivery else 'hls' if delivery == 'HLS' else 'other'
        key = (drm_profile(option), delivery)
        counts[key] = counts.get(key, 0) + 1
    return [dict(drm=drm, delivery=delivery, count=count)
            for (drm, delivery), count in sorted(counts.items())]


def smooth_candidates(medias):
    result = []
    def walk(node, depth=0):
        if depth > 8:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ('distribURL', 'manifestUrl', 'manifestURL', 'url', 'src') and isinstance(value, str):
                    try:
                        url = stream.checked_url(value)
                    except stream.StreamError:
                        continue
                    parts = urllib.parse.urlsplit(url)
                    path = parts.path.rstrip('/')
                    if path.casefold().endswith(('.ism', '.isml')):
                        result.append(urllib.parse.urlunsplit(parts._replace(path=path + '/manifest')))
                    elif re.search(r'\.(?:ism|isml)/manifest$', path, re.IGNORECASE):
                        result.append(url)
                elif isinstance(value, (dict, list)):
                    walk(value, depth + 1)
        elif isinstance(node, list):
            for value in node[:100]:
                walk(value, depth + 1)
    walk(medias)
    return list(dict.fromkeys(result))


def inspect_source_manifest(http, url):
    result = {}
    try:
        raw, _ = http.read(url)
        root = ET.fromstring(raw)
        name = root.tag.rsplit('}', 1)[-1].lower()
        result['result'] = ('smooth_streaming' if name == 'smoothstreamingmedia' else
                            'dash' if name == 'mpd' else 'other_xml')
        if name == 'smoothstreamingmedia':
            streams = [n for n in root if n.tag.rsplit('}', 1)[-1] == 'StreamIndex']
            result['stream_types'] = sorted({n.get('Type') for n in streams
                                             if n.get('Type') in ('audio', 'video', 'text')})
            result['video_heights'] = sorted({int(n.get('MaxHeight')) for s in streams
                if s.get('Type') == 'video' for n in s if n.get('MaxHeight', '').isdigit()
                and len(n.get('MaxHeight')) <= 5})
    except stream.StreamError as error:
        result['result'] = 'http_error' if error.reason == 'http_error' else 'source_unavailable'
    except (ET.ParseError, OSError, ValueError):
        result['result'] = 'source_invalid_or_unavailable'
    result.update(manifest_response_metadata(http))
    return result


def manifest_response_metadata(http):
    """Copy only transport status, never a URL, query, header or response body."""
    raw = getattr(http, 'last_response_metadata', {})
    result = {}
    for key in ('http_status', 'response_bytes'):
        value = raw.get(key)
        if isinstance(value, int) and not isinstance(value, bool): result[key] = value
    for key in ('response_content_type', 'response_content_encoding'):
        value = raw.get(key)
        if isinstance(value, str) and re.fullmatch(r'[a-z0-9.+/-]{1,80}', value): result[key] = value
    if isinstance(raw.get('response_redirected'), bool):
        result['response_redirected'] = raw['response_redirected']
    return result


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
