#!/usr/bin/env python3
"""Live TV remote switching: latest selection wins; decoder workers never overlap."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from test_epg import load_plugin_with_enigma_stubs

ENTRIES = [('Pierwszy', '11'), ('Drugi', '22'), ('Trzeci', '33')]


class ChannelSwitchTests(unittest.TestCase):
    def player(self, entries=ENTRIES):
        plugin = load_plugin_with_enigma_stubs()
        restored, stopped, closed = [], [], []
        session = SimpleNamespace(nav=SimpleNamespace(
            getCurrentlyPlayingServiceReference=lambda: 'original-service',
            stopService=lambda: stopped.append(True), playService=restored.append))
        player = plugin.CanalE2Player(session, '11', 'Pierwszy', entries)
        player.close = lambda: closed.append(True)
        return player, restored, stopped, closed

    def test_fast_channel_presses_stop_once_and_start_only_latest_after_old_exit(self):
        player, restored, stopped, closed = self.player()
        player.start()
        old = player.container
        old.sendCtrlC = Mock(wraps=old.sendCtrlC)
        player.on_data(b'{"stage":"player_running","selected_video_height":1080}\n')
        player['actions'].actions['pageUp']()
        player['actions'].actions['up']()
        self.assertEqual(player.pending_channel, ENTRIES[2])
        self.assertIs(player.container, old)
        self.assertEqual(player.channel_id, '11')
        self.assertEqual(old.sendCtrlC.call_count, 1)
        player.on_data(b'{"stage":"error","reason":"old_worker_error"}\n')
        self.assertIn('Trzeci', player['status'].text)
        self.assertNotIn('old_worker_error', player['status'].text)
        player.on_exit(-2)
        self.assertIsNone(player.container)
        self.assertEqual(player.channel_id, '33')
        self.assertIsNone(player.actual_height)
        self.assertEqual(player.epg, {})
        self.assertEqual(player.epg_loader.channel, '33')
        self.assertEqual(old.dataAvail, [])
        self.assertEqual(old.appClosed, [])
        self.assertFalse(closed or restored)
        player.start()
        self.assertIsNot(player.container, old)
        self.assertEqual(player.container.arguments[-3:], ('33', '--height', '4320'))
        self.assertEqual(len(stopped), 2)
        player.cleanup()
        self.assertEqual(restored, ['original-service'])

    def test_wrap_both_directions_and_single_channel_does_not_zap(self):
        player, restored, _, _ = self.player()
        player['actions'].actions['pageDown']()
        self.assertEqual(player.channel_id, '33')
        player['actions'].actions['up']()
        self.assertEqual(player.channel_id, '11')
        player['actions'].actions['down']()
        self.assertEqual(player.channel_id, '33')
        self.assertFalse(restored)
        player.cleanup()
        for entries in [ENTRIES[:1]]:
            player, _, _, _ = self.player(entries)
            player['actions'].actions['pageUp']()
            self.assertEqual(player.channel_id, '11')
            self.assertIsNone(player.pending_channel)
            player.cleanup()

    def test_exit_during_switch_cancels_next_channel_without_second_interrupt(self):
        player, restored, _, closed = self.player()
        player.start()
        old = player.container
        old.sendCtrlC = Mock(wraps=old.sendCtrlC)
        player.zap(1)
        player.stop()
        self.assertEqual(old.sendCtrlC.call_count, 1)
        self.assertIsNone(player.pending_channel)
        self.assertFalse(player.start_timer.active)
        player.on_exit(-2)
        self.assertEqual(closed, [True])
        player.start()
        self.assertIs(player.container, old)
        player.cleanup()
        self.assertEqual(restored, ['original-service'])

    def test_can_switch_after_channel_playback_error_without_leaving_player(self):
        player, restored, _, closed = self.player()
        player.start()
        old = player.container
        player.on_exit(1)
        self.assertFalse(player.running)
        player.zap(1)
        self.assertEqual(player.channel_id, '22')
        self.assertIsNone(player.container)
        self.assertEqual(old.appClosed, [])
        player.start()
        self.assertTrue(player.running)
        self.assertFalse(closed or restored)
        player.cleanup()


if __name__ == '__main__':
    unittest.main()
