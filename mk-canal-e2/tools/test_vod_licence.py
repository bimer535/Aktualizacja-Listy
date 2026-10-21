"""Licence URL integrity and bounded, redacted HTTP error reporting."""
import base64
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/CanalE2Test'))
import vod_api as api
import canal_stream_test_v2 as stream


class VodLicenceTests(unittest.TestCase):
    def test_signed_query_order_duplicates_and_encoding_are_kept_exactly(self):
        source = api.HAPI + '/licence?sig=PRIVATE%2B%2F%3D&part=a%20b&part=c+d&&x='
        target, supplied = api.licence_target(source)
        self.assertFalse(supplied)
        self.assertEqual(target, source + '&drmType=DRM_WIDEVINE')

    def test_service_drm_parameter_is_never_overwritten_or_reencoded(self):
        for query in ('drmType=DRM_WIDEVINE&sig=PRIVATE%2B',
                      'sig=PRIVATE&drm%54ype=DRM_WIDEVINE&part=a%20b&part=c+d'):
            source = api.HAPI + '/licence?' + query
            self.assertEqual(api.licence_target(source), (source, True))

    def test_empty_query_adds_exactly_one_drm_field(self):
        for suffix in ('', '?', '?sig=PRIVATE&'):
            target, supplied = api.licence_target('/licence' + suffix)
            self.assertEqual(target.count('drmType=DRM_WIDEVINE'), 1)
            self.assertFalse(supplied)

    def test_403_json_reports_only_codes_fields_and_fixed_hints(self):
        body = json.dumps({'error': {'code': 4031, 'message': 'Device hardware security level PRIVATE-TOKEN'},
                           'license': 'PRIVATE-LICENCE', 'LicenseInfo': 'PRIVATE-KEYS'}).encode()
        seen = []
        def opener(req, **kwargs):
            seen.append(req)
            raise urllib.error.HTTPError(req.full_url, 403, 'PRIVATE-REASON',
                {'Content-Type': 'application/json; charset=utf-8'}, io.BytesIO(body))
        client = api.VodApi({'passToken': 'PRIVATE-ACCOUNT'}, '11111111', opener=SimpleNamespace(open=opener))
        client.diagnostic = {'manifest_attempts': [{'result': 'mpd_loaded', 'http_status': 200}]}
        with self.assertRaises(stream.StreamError):
            client.licence('/licence?sig=PRIVATE%2B&part=1&part=2', b'PRIVATE-CHALLENGE')
        self.assertEqual(seen[0].data, base64.b64encode(b'PRIVATE-CHALLENGE'))
        self.assertEqual(seen[0].get_method(), 'POST')
        self.assertEqual(seen[0].get_header('Content-type'), 'text/plain')
        self.assertIn('part=1&part=2', seen[0].full_url)
        data = client.diagnostic['licence_http_error']
        self.assertEqual(data['service_codes'], {'code': 4031})
        self.assertIn('security_level_mentioned', data['message_hint_tags'])
        self.assertEqual(client.diagnostic['manifest_attempts'][0]['result'], 'mpd_loaded')
        for secret in ('PRIVATE', 'LicenseInfo', 'sig=', 'security level', 'CHALLENGE'):
            self.assertNotIn(secret, json.dumps(client.diagnostic))

    def test_non_json_http_error_is_not_interpreted_as_licence(self):
        body = io.BytesIO(b'PRIVATE-LICENCE-DATA')
        def opener(req, **kwargs):
            raise urllib.error.HTTPError(req.full_url, 403, 'Forbidden', {'Content-Type': 'text/html'}, body)
        client = api.VodApi({'passToken': 'PRIVATE'}, '11111111', opener=SimpleNamespace(open=opener))
        with patch.object(api, 'error_shape', side_effect=AssertionError('parsed non-JSON data')):
            with self.assertRaises(stream.StreamError): client.licence('/licence', b'challenge')
        self.assertTrue(body.closed)
        self.assertNotIn('PRIVATE', json.dumps(client.diagnostic))

    def test_successful_licence_body_is_never_sent_to_error_inspector(self):
        class Response(io.BytesIO):
            pass
        raw = b'\x08\x01\x12\x03abc'
        client = api.VodApi({'passToken': 'PRIVATE'}, '11111111',
                            opener=SimpleNamespace(open=lambda *args, **kwargs: Response(raw)))
        with patch.object(api, 'error_shape', side_effect=AssertionError('inspected valid licence')):
            self.assertEqual(client.licence('/licence', b'challenge'), raw)
        self.assertNotIn('abc', json.dumps(client.diagnostic))

    def test_nested_service_failure_does_not_export_licence_or_device_values(self):
        result = api.error_shape(json.dumps({'ServiceResponse': {'OutData': {
            'Status': '-200', 'StatusMessage': 'Device PRIVATE-DEVICE',
            'LicenseInfo': 'PRIVATE-LICENCE', 'private_key': 'PRIVATE-KEY'}}}).encode())
        self.assertEqual(result['service_codes'], {'Status': -200})
        self.assertIn('device_mentioned', result['message_hint_tags'])
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertNotIn('LicenseInfo', json.dumps(result))


if __name__ == '__main__':
    unittest.main()
