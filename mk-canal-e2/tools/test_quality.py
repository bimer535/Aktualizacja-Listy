"""Exact rendition selection, including equal-height bitrates and Dolby audio."""
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/CanalE2Test'))
import quality
import player_runtime as runtime
from test_epg import load_plugin_with_enigma_stubs


def manifest():
    return ET.fromstring('''<MPD><Period><AdaptationSet mimeType="video/mp4" codecs="avc1.64002a">
      <Representation id="top" width="1920" height="1080" bandwidth="8000000" frameRate="50"/>
      <Representation id="mid50" width="960" height="540" bandwidth="2500000" frameRate="50"/>
      <Representation id="mid25" width="960" height="540" bandwidth="1500000" frameRate="25"/>
      </AdaptationSet><AdaptationSet mimeType="audio/mp4" lang="pl" codecs="mp4a.40.2">
      <Representation id="aac" bandwidth="128000"/></AdaptationSet>
      <AdaptationSet mimeType="audio/mp4" lang="pl" codecs="ec-3">
      <Representation id="dolby" bandwidth="210000"/></AdaptationSet></Period></MPD>''')


class QualityTests(unittest.TestCase):
    def test_remote_can_navigate_quality_dialog_and_cancel_it(self):
        plugin = load_plugin_with_enigma_stubs()
        choices = [{'label': quality.label(meta), 'preference': meta} for meta, _, _ in quality.variants(manifest())]
        dialog = plugin.CanalE2Quality(SimpleNamespace(), 'Test', choices)
        dialog.close = Mock()
        dialog['actions'].actions['down']()
        dialog['actions'].actions['ok']()
        dialog.close.assert_called_once_with(1)
        dialog.close.reset_mock()
        dialog['actions'].actions['cancel']()
        dialog.close.assert_called_once_with(None)

    def test_all_bitrates_framerates_and_audio_variants_remain_selectable(self):
        options = quality.variants(manifest())
        self.assertEqual(len(options), 6)
        self.assertEqual(quality.label(options[0][0]), '[pl] bitrate: 8128000  1920x1080  mp4a,avc1 50 kl./s')
        self.assertEqual({m['fps'] for m, _, _ in options if m['height'] == 540}, {25, 50})
        self.assertEqual({m['audio_codec'] for m, _, _ in options}, {'mp4a', 'ec-3'})
        self.assertAlmostEqual(quality.fps('30000/1001'), 29.97)
        for invalid in ('1/0', 'private data', '', '9999'):
            self.assertEqual(quality.fps(invalid), 0)

    def test_selected_lower_bitrate_and_dolby_survive_manifest_filtering(self):
        root = manifest()
        events = []
        video, audio = quality.choose(root, lambda stage, **kw: events.append((stage, kw)),
                                      io.StringIO('bad\n{"quality_index":true}\n{"quality_index":5}\n'))
        self.assertEqual((video['id'], audio['id']), ('mid25', 'dolby'))
        serialized, identity = runtime.filtered_manifest(root, 'https://cdn.example/movie.mpd', 540,
            video_reference=runtime.track_reference(video), audio_reference=runtime.track_reference(audio))
        kept = ET.fromstring(serialized)
        self.assertEqual([node.get('id') for node in kept.iter('Representation')], ['mid25', 'dolby'])
        fresh = manifest()
        refreshed, _ = runtime.filtered_manifest(fresh, 'https://cdn.example/movie.mpd', 540, identity,
            runtime.track_reference(video), runtime.track_reference(audio))
        self.assertEqual(serialized, refreshed)
        self.assertEqual(events[0][0], 'quality_choices')
        safe = json.dumps(events)
        for forbidden in ('cdn.example', 'Representation', 'mid25', 'dolby'):
            self.assertNotIn(forbidden, safe)

    def test_channel_change_matches_preference_without_reopening_quality_menu(self):
        options = quality.variants(manifest())
        preference = options[5][0]
        events = []
        video, audio = quality.choose(manifest(), lambda s, **kw: events.append(s), None, preference)
        self.assertEqual((video['id'], audio['id']), ('mid25', 'dolby'))
        self.assertEqual(events, ['quality_chosen'])
        options = [item for item in options if item[0]['height'] != 1080]
        chosen = quality.preferred_index(options, dict(preference, height=1080, fps=50))
        self.assertEqual(options[chosen][1]['id'], 'mid50')
        self.assertEqual(options[chosen][2]['id'], 'dolby')

    def test_cancel_does_not_request_licence(self):
        with self.assertRaisesRegex(runtime.StreamError, 'quality_selection_cancelled'):
            quality.choose(manifest(), lambda *a, **kw: None, io.StringIO(''))

    def test_gui_selection_sends_index_and_zap_reuses_quality_properties(self):
        plugin = load_plugin_with_enigma_stubs()
        callbacks = []
        session = SimpleNamespace(nav=SimpleNamespace(getCurrentlyPlayingServiceReference=lambda: None,
                  stopService=lambda: None), openWithCallback=lambda cb, *args: callbacks.append(cb))
        player = plugin.CanalE2Player(session, '11', 'Test', channel_list=[('Test', '11'), ('Inny', '22')])
        player.start()
        self.assertIn('--choose-quality', player.container.arguments)
        player.container.write = Mock()
        choices = [{'label': quality.label(meta), 'preference': meta} for meta, _, _ in quality.variants(manifest())]
        player.on_data((json.dumps({'stage': 'quality_choices', 'quality_choices': choices}) + '\n').encode())
        callbacks[0](5)
        player.container.write.assert_called_once_with(b'{"quality_index": 5}\n')
        self.assertEqual(player.quality_preference['fps'], 25)
        player.zap(1)
        player.on_exit(0)
        player.start()
        self.assertIn('--quality-preference', player.container.arguments)
        self.assertNotIn('--choose-quality', player.container.arguments)
        player.cleanup()


if __name__ == '__main__':
    unittest.main()
