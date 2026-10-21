"""Session recovery is bounded and does not alter healthy/other error paths."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/CanalE2Test'))
import session_recover as recovery
import canal_channels_test as channels
import account_worker
from test_session_recover import SAVED, RENEWED

GOOD = {'ServiceResponse': {'OutData': {'PDS': {}}}}
BAD = {'ServiceResponse': {'Status': -3}}
IDS = {'UserKeyId': '11111111-1111-1111-1111-111111111111', 'DeviceKeyId': '22222222-2222-2222-2222-222222222222'}
ENTRIES = [{'name': 'Test HD', 'epg_id': '1', 'authorized': True}]


class AutoRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'session.json'
        channels.atomic_private_json(self.path, SAVED)
        channels.atomic_private_json(self.path.with_name('client.json'), IDS)

    def test_healthy_session_does_not_request_renewal(self):
        event = Mock()
        with patch.object(channels, 'fetch_init', return_value=GOOD) as fetch, \
             patch.object(recovery, 'recover') as renew:
            saved, ids, response, out = recovery.load_live_session(self.path, channels, event)
        self.assertEqual(saved, SAVED)
        self.assertEqual(ids, IDS)
        self.assertEqual(response, GOOD)
        renew.assert_not_called()
        event.assert_not_called()
        self.assertEqual(fetch.call_count, 1)

    def test_live_minus_three_renews_once_and_reuses_validated_response(self):
        event = Mock()
        with patch.object(channels, 'fetch_init', side_effect=[BAD, GOOD]) as fetch, \
             patch.object(channels, 'normalize_channels', return_value=ENTRIES), \
             patch.object(recovery, 'renew', return_value=RENEWED) as renew:
            saved, ids, response, out = recovery.load_live_session(self.path, channels, event)
        renew.assert_called_once()
        event.assert_called_once_with('renew_session')
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(saved['authentication']['passToken'], RENEWED['passToken'])
        self.assertEqual(response, GOOD)
        self.assertEqual(ids, IDS)

    def test_other_service_status_and_http_error_do_not_renew(self):
        failures = [({'ServiceResponse': {'Status': -1}}, None),
                    (None, channels.ChannelError('http_error', http_status=403))]
        for response, error in failures:
            with self.subTest(response=response), \
                 patch.object(channels, 'fetch_init', return_value=response, side_effect=error), \
                 patch.object(recovery, 'recover') as renew:
                with self.assertRaises(channels.ChannelError):
                    recovery.load_live_session(self.path, channels)
                renew.assert_not_called()

    def test_failed_renewal_preserves_session_and_reports_safe_channel_error(self):
        before = self.path.read_bytes()
        with patch.object(channels, 'fetch_init', return_value=BAD), \
             patch.object(recovery, 'renew', side_effect=recovery.RecoveryError('token_refresh_http_error', http_status=403)) as renew:
            with self.assertRaises(channels.ChannelError) as result:
                recovery.load_live_session(self.path, channels)
        renew.assert_called_once()
        self.assertEqual(result.exception.reason, 'token_refresh_http_error')
        self.assertEqual(result.exception.details, {'http_status': 403})
        self.assertEqual(self.path.read_bytes(), before)

    def test_live_rejection_after_renewal_does_not_loop_or_save(self):
        before = self.path.read_bytes()
        with patch.object(channels, 'fetch_init', return_value=BAD) as fetch, \
             patch.object(recovery, 'renew', return_value=RENEWED) as renew:
            with self.assertRaises(channels.ChannelError):
                recovery.load_live_session(self.path, channels)
        renew.assert_called_once()
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(self.path.read_bytes(), before)

    def test_account_refresh_uses_same_recovery_and_saves_channels(self):
        with patch.object(channels, 'fetch_init', side_effect=[BAD, GOOD]), \
             patch.object(channels, 'normalize_channels', return_value=ENTRIES), \
             patch.object(recovery, 'renew', return_value=RENEWED), \
             patch.object(account_worker, 'emit') as event:
            self.assertTrue(account_worker.refresh(self.path))
        self.assertIn(unittest.mock.call('renew_session'), event.call_args_list)
        event.assert_any_call('channels_loaded', channel_count=1)
        self.assertEqual(channels.load_json(self.path.with_name('live.json'))['channels'], ENTRIES)


if __name__ == '__main__':
    unittest.main()
