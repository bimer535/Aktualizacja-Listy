"""Failed token recovery must leave the existing paired identity untouched."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/CanalE2Test'))
import canal_channels_test as channels
import session_recover as recover

SAVED = {'schema_version': 1, 'device_id': '11111111-1111-1111-1111-111111111111',
         'authentication': {'passId': 'PRIVATE-IDENTITY', 'passToken': 'PRIVATE-OLD-TOKEN'}}
RENEWED = {'errorCode': 0, 'passId': 'PRIVATE-RENEWED-ID', 'passToken': 'PRIVATE-NEW-TOKEN',
           'userData': {'isAuthenticated': True}}


class Response(io.BytesIO):
    code = 200


class RecoveryTests(unittest.TestCase):
    def test_renewal_uses_existing_device_identity_and_official_service(self):
        seen = []
        def open_request(request, **kwargs):
            seen.append(request)
            self.assertEqual(kwargs['timeout'], 25)
            return Response(json.dumps({'response': RENEWED}).encode())
        self.assertEqual(recover.renew(SAVED, Mock(open=open_request)), RENEWED)
        request = seen[0]
        fields = recover.urllib.parse.parse_qs(request.data.decode())
        self.assertEqual(request.full_url, recover.TOKEN_URL)
        self.assertEqual(fields['passId'], ['PRIVATE-IDENTITY'])
        self.assertEqual(fields['deviceId'], [SAVED['device_id']])
        self.assertNotIn('PRIVATE-OLD-TOKEN', request.data.decode())

    def test_invalid_identity_is_not_sent(self):
        opener = Mock()
        with self.assertRaisesRegex(recover.RecoveryError, 'paired_identity_missing'):
            recover.renew({'authentication': {}}, opener)
        opener.open.assert_not_called()

    def test_rejected_or_prospect_response_is_not_accepted(self):
        for data in ({'errorCode': 1}, dict(RENEWED, userData={'isAuthenticated': False}),
                     {'errorCode': 0, 'passId': 'some-id'}):
            with self.subTest(data=data):
                opener = Mock(open=lambda *a, **kw: Response(json.dumps({'response': data}).encode()))
                with self.assertRaises(recover.RecoveryError):
                    recover.renew(SAVED, opener)

    def test_failed_live_validation_does_not_change_account_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'session.json'
            channels.atomic_private_json(path, SAVED)
            channels.atomic_private_json(path.with_name('client.json'), {'UserKeyId': 'same-user', 'DeviceKeyId': 'same-device'})
            before = path.read_bytes()
            with patch.object(recover, 'renew', return_value=RENEWED), \
                 patch.object(channels, 'fetch_init', side_effect=channels.ChannelError('http_error', http_status=403)):
                with self.assertRaises(channels.ChannelError):
                    recover.recover(path, channels)
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse(path.with_name('live.json').exists())

    def test_success_saves_only_after_authorized_channels_are_loaded(self):
        response = {'ServiceResponse': {'OutData': {'PDS': {}}}}
        entries = [{'name': 'Example', 'epg_id': '1', 'authorized': True}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'session.json'
            channels.atomic_private_json(path, SAVED)
            ids = {'UserKeyId': 'same-user', 'DeviceKeyId': 'same-device'}
            channels.atomic_private_json(path.with_name('client.json'), ids)
            with patch.object(recover, 'renew', return_value=RENEWED), \
                 patch.object(channels, 'fetch_init', return_value=response) as fetch, \
                 patch.object(channels, 'normalize_channels', return_value=entries):
                self.assertEqual(recover.recover(path, channels), 1)
            request = fetch.call_args.args[0]['ServiceRequest']['InData']
            self.assertEqual(request['PassData']['Token'], 'PRIVATE-NEW-TOKEN')
            self.assertEqual(request['DeviceKeyId'], ids['DeviceKeyId'])
            self.assertEqual(channels.load_json(path)['device_id'], SAVED['device_id'])
            self.assertEqual(channels.load_json(path)['authentication']['passToken'], 'PRIVATE-NEW-TOKEN')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_no_authorized_channels_keeps_old_session(self):
        fake = Mock()
        fake.load_json.side_effect = [SAVED, {'UserKeyId': 'same', 'DeviceKeyId': 'same'}]
        fake.normalize_channels.return_value = [{'authorized': False}]
        with patch.object(recover, 'renew', return_value=RENEWED):
            with self.assertRaisesRegex(recover.RecoveryError, 'renewed_identity_has_no_authorized_channels'):
                recover.recover(Path('/example/session.json'), fake)
        fake.atomic_private_json.assert_not_called()

    def test_identity_cannot_be_redirected_to_another_service(self):
        redirect = recover.SameTokenOrigin()
        request = urllib.request.Request(recover.TOKEN_URL, data=b'private-identity')
        with self.assertRaisesRegex(recover.RecoveryError, 'unexpected_token_redirect'):
            redirect.redirect_request(request, None, 302, '', {}, 'https://other.example/collect')


if __name__ == '__main__':
    unittest.main()
