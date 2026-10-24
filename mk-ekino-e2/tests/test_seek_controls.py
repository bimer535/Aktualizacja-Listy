import json
from pathlib import Path
import tempfile
import types
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch
from test_gui import load_ui

ROOT = Path(__file__).resolve().parents[1]


class SeekControlsTests(unittest.TestCase):
    def setUp(self):
        self.ui = load_ui()
        self.session = Mock()
        self.seek = Mock()
        self.seek.isCurrentlySeekable.return_value = 3
        self.seek.getPlayPosition.return_value = (0, 300 * 90000)
        self.seek.getLength.return_value = (0, 3600 * 90000)
        self.seek.seekTo.return_value = 0
        self.seek.seekRelative.return_value = 0
        self.service = self.session.nav.getCurrentService.return_value
        self.service.seek.return_value = self.seek
        self.service.pause.return_value.setFastForward.side_effect = AssertionError('Trick mode must not be used')
        self.player = self.ui.EkinoMoviePlayer(self.session, 'service', mk_resume=1200, fromMovieSelection=False)
        self.actions = self.player['mkSeekActions']
        self.helper = __import__(self.player.__class__.__mro__[1].__module__, fromlist=['time'])

    def test_both_controls_use_time_seek_without_native_fast_winding(self):
        for action, delta in [('left', -10), ('right', 10)]:
            with self.subTest(action=action):
                self.player._mk_seek_target = None
                self.seek.seekTo.reset_mock()
                self.assertEqual(self.actions.actions[action](), 1)
                self.seek.seekTo.assert_called_once_with((300 + delta) * 90000)
        self.service.pause.return_value.setFastForward.assert_not_called()
        self.assertLess(self.actions.priority, self.player['mkPauseActions'].priority)

    def test_fast_repeated_presses_accumulate_with_stale_backend_position(self):
        with patch.object(self.helper.time, 'monotonic', return_value=100):
            for _ in range(3): self.actions.actions['right']()
            self.actions.actions['left']()
        self.assertEqual([c.args[0] // 90000 for c in self.seek.seekTo.call_args_list], [310, 320, 330, 320])

    def test_pending_target_expires_when_backend_did_not_move(self):
        with patch.object(self.helper.time, 'monotonic', return_value=100): self.player.mk_jump(10)
        with patch.object(self.helper.time, 'monotonic', return_value=104): self.player.mk_jump(10)
        self.assertEqual([c.args[0] // 90000 for c in self.seek.seekTo.call_args_list], [310, 310])

    def test_caught_up_position_is_not_double_counted(self):
        self.player.mk_jump(10)
        self.seek.getPlayPosition.return_value = (0, 311 * 90000)
        self.player.mk_jump(10)
        self.assertEqual(self.seek.seekTo.call_args.args[0], 321 * 90000)

    def test_bounds_do_not_send_a_target_beyond_duration(self):
        self.seek.getPlayPosition.return_value = (0, 3 * 90000)
        self.player.mk_jump(-60)
        self.seek.seekTo.assert_called_with(0)
        self.player._mk_seek_target = None
        self.seek.getPlayPosition.return_value = (0, 3595 * 90000)
        self.player.mk_jump(60)
        self.seek.seekTo.assert_called_with(3599 * 90000)

    def test_successful_user_jump_cancels_automatic_resume_retry(self):
        self.player.mk_jump(10)
        self.assertEqual(self.player.mk_resume, 0)
        self.assertFalse(self.player.mk_seek_sent)

    def test_pause_is_preserved(self):
        self.player.pauseService()
        self.player.mk_jump(10)
        self.assertEqual(self.player.seekstate, self.player.SEEK_STATE_PAUSE)
        self.service.pause.return_value.pause.assert_called_once_with()
        self.assertEqual(self.player.unpause_count, 0)

    def test_no_seek_interface_is_consumed_and_notifies_once(self):
        self.service.seek.return_value = None
        self.assertEqual(self.player.mk_jump(10), 1)
        self.assertEqual(self.player.mk_jump(10), 1)
        self.session.open.assert_called_once()
        self.seek.seekTo.assert_not_called()

    def test_seek_rejected_never_falls_through_to_native_speed_mode(self):
        self.seek.seekTo.return_value = -1; self.seek.seekRelative.return_value = -1
        self.assertEqual(self.player.mk_jump(-10), 1)
        self.session.open.assert_called_once()
        self.service.pause.return_value.setFastForward.assert_not_called()

    def test_relative_fallback_and_unknown_position(self):
        self.seek.seekTo.return_value = -1
        self.player.mk_jump(-10)
        self.seek.seekRelative.assert_called_with(-1, 10 * 90000)
        self.seek.getPlayPosition.return_value = (-1, 0)
        self.seek.seekTo.reset_mock(); self.seek.seekRelative.reset_mock()
        self.player.mk_jump(10)
        self.seek.seekTo.assert_not_called()
        self.seek.seekRelative.assert_called_once_with(1, 10 * 90000)

    def test_backend_exception_and_closed_player_are_safe(self):
        self.seek.seekTo.side_effect = RuntimeError('backend unavailable')
        self.assertEqual(self.player.mk_jump(10), 1)
        self.session.open.assert_called_once()
        self.seek.seekTo.reset_mock(); self.player.mk_leaving = True
        self.assertEqual(self.player.mk_jump(10), 1)
        self.seek.seekTo.assert_not_called()

    def test_ok_exit_and_numeric_keys_are_not_in_private_seek_context(self):
        mapping = ET.parse(ROOT/'src/MKEkinoE2/seek_keymap.xml').find('map')
        self.assertEqual(self.actions.contexts, [mapping.attrib['context']])
        self.assertFalse({k.attrib['id'] for k in mapping} & {'KEY_OK', 'KEY_EXIT', 'KEY_1', 'KEY_3', 'KEY_6', 'KEY_9'})

    def test_real_image_bindings_dispatch_one_jump_for_each_short_press(self):
        images = json.loads((ROOT/'tests/seek_keymaps.json').read_text())['maps']
        private = [dict(key.attrib, context=self.actions.contexts[0]) for key in ET.parse(ROOT/'src/MKEkinoE2/seek_keymap.xml').find('map')]
        for image, native in images.items():
            for key, delta in [('KEY_LEFT', -10), ('KEY_RIGHT', 10)]:
                with self.subTest(image=image, key=key):
                    self.player._mk_seek_target = None; self.seek.seekTo.reset_mock()
                    native_called = []
                    self.dispatch(private, native, key, ['m', 'b'], native_called)
                    self.assertEqual([c.args[0] for c in self.seek.seekTo.call_args_list], [(300 + delta) * 90000])
                    self.assertEqual(native_called, [])

    def test_long_transport_key_has_no_extra_short_jump_on_release(self):
        private = [dict(key.attrib, context=self.actions.contexts[0]) for key in ET.parse(ROOT/'src/MKEkinoE2/seek_keymap.xml').find('map')]
        images = json.loads((ROOT/'tests/seek_keymaps.json').read_text())['maps']
        for image, native in images.items():
          for events in (['m', 'b'], ['m', 'l', 'b']):
            for key, delta in [('KEY_REWIND', -60), ('KEY_FASTFORWARD', 60)]:
                with self.subTest(image=image, key=key):
                    self.player._mk_seek_target = None; self.player._mk_scrub_speed = 0; self.seek.seekTo.reset_mock()
                    native_called=[]; self.dispatch(private,native,key,events,native_called)
                    self.seek.seekTo.assert_not_called()
                    self.assertEqual(self.player._mk_scrub_speed, 2 if delta > 0 else -2)
                    self.assertEqual(native_called, [])


    def test_scrub_speed_selection_and_commit_with_ok(self):
        with patch.object(self.helper.time, 'monotonic', return_value=100):
            self.actions.actions['seekFwd']()
        self.assertEqual(self.player._mk_scrub_speed, 2)
        self.seek.seekTo.assert_not_called()
        self.assertEqual(self.player.seekstate, self.player.SEEK_STATE_PAUSE)
        with patch.object(self.helper.time, 'monotonic', return_value=105):
            self.player.mk_seek_refresh()
            self.actions.actions['seekFwd']()
        self.assertEqual(self.player._mk_scrub_speed, 4)
        self.assertIn('x4', self.player._mk_seek_display_mode)
        self.assertEqual(self.player._mk_seek_display_target, 310 * 90000)
        with patch.object(self.helper.time, 'monotonic', return_value=110):
            self.player.mk_toggle_pause()
        self.seek.seekTo.assert_called_once_with(330 * 90000)
        self.assertEqual(self.player._mk_scrub_speed, 0)
        self.assertEqual(self.player.seekstate, self.player.SEEK_STATE_PLAY)

    def test_scrub_bounds_reverse_and_speed_cap(self):
        with patch.object(self.helper.time, 'monotonic', return_value=100):
            for _ in range(9): self.actions.actions['seekFwd']()
        self.assertEqual(self.player._mk_scrub_speed, 64)
        with patch.object(self.helper.time, 'monotonic', return_value=200):
            self.player.mk_seek_refresh()
        self.assertEqual(self.player._mk_seek_display_target, 3599 * 90000)
        with patch.object(self.helper.time, 'monotonic', return_value=200):
            self.actions.actions['seekBack']()
        self.assertEqual(self.player._mk_scrub_speed, -2)
        with patch.object(self.helper.time, 'monotonic', return_value=4000):
            self.player.mk_seek_refresh()
        self.assertEqual(self.player._mk_seek_display_target, 0)

    def test_jump_osd_shows_target_and_actual_separately(self):
        self.player.mk_jump(10)
        dialog = self.session.instantiateDialog.return_value
        mode, target, length, actual, selecting = dialog.update.call_args.args
        self.assertIn('+10', mode)
        self.assertEqual((target, length, actual, selecting), (310*90000, 3600*90000, 300*90000, False))
        self.seek.getPlayPosition.return_value = (0, 311 * 90000)
        self.player.mk_seek_refresh()
        self.assertEqual(dialog.update.call_args.args[3], 311 * 90000)
        with patch.object(self.helper.time, 'monotonic', return_value=self.player._mk_seek_visible_until + 1):
            self.player.mk_seek_refresh()
        dialog.hide.assert_called()

    def test_overlay_skin_and_timecodes(self):
        self.helper.getDesktop.return_value.size.return_value.width.return_value = 1920
        self.helper.getDesktop.return_value.size.return_value.height.return_value = 1080
        dialog = self.helper.SeekStatus(self.session)
        ET.fromstring(dialog.skin)
        dialog.update('Skok +10 s', 3661 * 90000, 7200 * 90000, 3600 * 90000, False)
        self.assertIn('01:01:01 / 02:00:00', dialog['position'].text)
        self.assertIn('01:00:00', dialog['position'].text)
        dialog['progress'].setValue.assert_called_with(50)
        dialog.update('Wybór pozycji >> x4', 0, None, None, True)
        self.assertIn('--:--:--', dialog['position'].text)
        self.assertIn('OK / PLAY', dialog['hint'].text)

    def test_scrub_cleanup_and_service_loss(self):
        self.player.mk_scrub(1)
        self.player.mk_seek_cleanup()
        self.assertEqual(self.player._mk_scrub_speed, 0)
        self.assertNotIn(self.player.mk_seek_refresh, self.player._mk_seek_timer.callback)
        self.session.deleteDialog.assert_called_once()
        self.player.mk_scrub(1)
        self.service.seek.return_value = None
        self.assertTrue(self.player.mk_scrub_finish())
        self.session.open.assert_called()

    def test_play_and_pause_commit_and_dpad_returns_to_time_jumps(self):
        with patch.object(self.helper.time, 'monotonic', return_value=100): self.player.mk_scrub(1)
        with patch.object(self.helper.time, 'monotonic', return_value=105): self.player.mk_seek_pause()
        self.assertEqual(self.player.seekstate, self.player.SEEK_STATE_PAUSE)
        self.assertEqual(self.player._mk_scrub_speed, 0)
        self.player.mk_seek_play()
        self.assertEqual(self.player.seekstate, self.player.SEEK_STATE_PLAY)
        self.player.mk_scrub(1)
        self.player.mk_seek_forward()
        self.assertEqual(self.player._mk_scrub_speed, 0)

    def dispatch(self, private, native, key, events, native_called):
        # OpenPLi lib/actions/action.cpp: all bindings record make/long first,
        # break after long is suppressed, then callbacks run until return 1.
        long_pressed = False
        for flag in events:
            if flag == 'm': long_pressed = False
            if flag == 'l': long_pressed = True
            if flag == 'b' and long_pressed: continue
            candidates = [(self.actions.priority, row, True) for row in private] + [(0, row, False) for row in native]
            for priority, row, own in sorted(candidates,key=lambda v:v[0]):
                if row['id'] != key or flag not in row['flags']: continue
                if own:
                    if self.actions.actions[row['mapto']](): break
                else:
                    native_called.append(row['mapto']); break

    def test_openpli_and_openatv_constructor_compatibility(self):
        original = self.ui.MoviePlayer.__init__; calls=[]
        def pli_init(instance,session,service,slist=None,lastservice=None,infobar=None):
            calls.append('pli'); original(instance,session,service)
        def atv_init(instance,session,service,fromMovieSelection=True):
            calls.append(fromMovieSelection); original(instance,session,service)
        for init in (pli_init,atv_init):
            with patch.object(self.ui.MoviePlayer,'__init__',init):
                player = self.ui.EkinoMoviePlayer(self.session,'service',fromMovieSelection=False)
                self.assertIn('mkSeekActions',player)
        self.assertEqual(calls,['pli',False])
