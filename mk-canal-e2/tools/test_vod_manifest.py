#!/usr/bin/env python3
"""VOD CDN boundary tests: signed query, headers, fallback and proxy refresh."""
import io
import json
from email.message import Message
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SOURCE = Path(__file__).resolve().parents[1] / 'src/CanalE2Test'
sys.path.insert(0, str(SOURCE))
import canal_stream_test_v2 as stream
import vod_api as api
from vod_data import CATALOGUE_USER_AGENT
import playback_worker as worker

MPD = b'<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static"><Period /></MPD>'


class Response(io.BytesIO):
    def __init__(self, body, url, status=200, mime='application/dash+xml'):
        super().__init__(body)
        self.url, self.code = url, status
        self.headers = Message()
        self.headers['Content-Type'] = mime


def client_for(medias, handler):
    media_http = stream.Http(user_agent=CATALOGUE_USER_AGENT)
    media_http.opener = SimpleNamespace(open=handler)
    client = api.VodApi({'passToken': 'PRIVATE-ACCOUNT'}, '11111111', media_http=media_http)
    option = {k: 'example' for k in ('comMode', 'contentId', 'distMode', 'distTechnology',
                                    'drmType', 'functionalType', 'hash', 'idKey', 'quality')}
    option.update(drmType='DRM_COMMON_ENCRYPTION', distTechnology='DASH', quality='HD')
    client.request = Mock(side_effect=[{'available': [option]},
        {'@medias': '/medias/1', '@licence': '/licence/1'}, medias])
    return client


class VodManifestTests(unittest.TestCase):
    def test_packager_suffix_is_added_before_signed_query_without_reencoding(self):
        query = 'token=SECRET%2B%2F%3D&Policy=first%26second&Policy=duplicate'
        for suffix, output in [('.ism', '.ism/manifest(format=mpd-time-csf)'),
                               ('.isml/', '.isml/manifest(format=mpd-time-csf)'),
                               ('.ism/Manifest', '.ism/Manifest(format=mpd-time-csf)')]:
            source = 'https://cdn.example/Film' + suffix + '?' + query
            expected = 'https://cdn.example/Film' + output + '?' + query
            self.assertEqual(api.manifest_candidates([{'files': [{'distribURL': source}]}]), [expected])
            self.assertEqual(urllib.parse.urlsplit(expected).query, query)

    def test_provider_dash_urls_remain_exact_and_keep_provider_order(self):
        urls = ['https://cdn.example/Film.mpd?token=SECRET%2B%2F',
                'https://backup.example/Film.ism/Manifest(format=mpd-time-csf)?t=SECOND']
        medias = [{'files': [{'distribURL': 'https://cdn.example/fallback.ism'},
                            *[{'distribURL': url} for url in urls]]}]
        self.assertEqual(api.manifest_candidates(medias)[:2], urls)

    def test_real_resolver_sends_browser_header_and_no_account_credentials_to_cdn(self):
        source = 'https://cdn.example/Film.ism?token=SECRET%2B%2F'
        expected = 'https://cdn.example/Film.ism/manifest(format=mpd-time-csf)?token=SECRET%2B%2F'
        seen = []
        def open_request(req, **kwargs):
            seen.append(req)
            self.assertEqual(req.full_url, expected)
            self.assertEqual(req.get_header('User-agent'), CATALOGUE_USER_AGENT)
            self.assertFalse(req.has_header('Authorization'))
            self.assertFalse(req.has_header('Cookie'))
            return Response(MPD, req.full_url)
        client = client_for([{'files': [{'distribURL': source}]}], open_request)
        root, final_url, licence = client.resolve('123_70026')
        self.assertEqual(root.tag.rsplit('}', 1)[-1], 'MPD')
        self.assertEqual(final_url, expected)
        self.assertEqual(len(seen), 1)
        self.assertEqual(client.diagnostic['manifest_attempts'][0]['result'], 'mpd_loaded')
        self.assertNotIn('SECRET', json.dumps(client.diagnostic))
        self.assertNotIn('cdn.example', json.dumps(client.diagnostic))

    def test_503_reports_candidate_kind_and_metadata_without_signed_url_or_body(self):
        source = 'https://cdn.example/Film.ism?token=SECRET'
        def open_request(req, **kwargs):
            return Response(b'PRIVATE-RESPONSE-SECRET', req.full_url, 503, 'text/html')
        client = client_for([{'files': [{'distribURL': source}]}], open_request)
        with self.assertRaises(stream.StreamError) as caught:
            client.resolve('123_70026')
        self.assertEqual(caught.exception.reason, 'vod_dash_manifest_unavailable')
        self.assertEqual(caught.exception.details['http_status'], 503)
        attempt = client.diagnostic['manifest_attempts'][0]
        self.assertEqual(attempt['candidate_type'], 'packager_dash')
        self.assertTrue(attempt['has_query_parameters'])
        self.assertEqual(attempt['http_status'], 503)
        self.assertEqual(attempt['response_content_type'], 'text/html')
        encoded = json.dumps(client.diagnostic)
        for private in ('SECRET', 'PRIVATE-RESPONSE', 'cdn.example', 'Film.ism'):
            self.assertNotIn(private, encoded)

    def test_second_provided_manifest_is_tried_after_first_returns_503(self):
        seen = []
        def open_request(req, **kwargs):
            seen.append(req.full_url)
            return Response(MPD, req.full_url, 503 if len(seen) == 1 else 200)
        urls = ['https://first.example/movie.mpd?token=A', 'https://second.example/movie.mpd?token=B']
        client = client_for([{'files': [{'distribURL': url} for url in urls]}], open_request)
        _, final, _ = client.resolve('123_70026')
        self.assertEqual(seen, urls)
        self.assertEqual(final, urls[1])
        self.assertEqual([a['http_status'] for a in client.diagnostic['manifest_attempts']], [503, 200])

    def test_live_default_headers_are_preserved_and_vod_headers_reach_initialization(self):
        for vod, expected in [(False, 'Mozilla/5.0 (X11; Linux armv7l) CANAL-E2-Stream-Test/0.1'),
                              (True, CATALOGUE_USER_AGENT)]:
            http = stream.Http(user_agent=CATALOGUE_USER_AGENT) if vod else stream.Http()
            seen = []
            def open_request(req, **kwargs):
                seen.append(req)
                return Response(b'init-data', req.full_url)
            http.opener = SimpleNamespace(open=open_request)
            http.read('https://cdn.example/init.mp4?token=SECRET')
            self.assertEqual(seen[0].get_header('User-agent'), expected)
        self.assertEqual(worker.native_user_agent(False), 'Mozilla/5.0')
        self.assertEqual(worker.native_user_agent(True), CATALOGUE_USER_AGENT)

    def test_manifest_proxy_refresh_uses_same_vod_http_client(self):
        remote = SimpleNamespace(read=Mock(return_value=(MPD, 'https://cdn.example/movie.mpd?token=SECRET')))
        errors = []
        with patch.object(worker.runtime, 'filtered_manifest', return_value=(MPD, ('tracks',))), \
             patch.object(worker.stream, 'Http', side_effect=AssertionError('VOD used default HTTP client')):
            server, url = worker.start_manifest_server('https://cdn.example/movie.mpd?token=SECRET',
                ET.fromstring(MPD), 1080, errors.append, http=remote)
            try:
                # First delivery is the prepared MPD. Second triggers a remote refresh.
                for _ in range(2):
                    with urllib.request.urlopen(url, timeout=3) as response:
                        self.assertEqual(response.read(), MPD)
            finally:
                server.shutdown(); server.server_close()
        remote.read.assert_called_once_with('https://cdn.example/movie.mpd?token=SECRET')
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
