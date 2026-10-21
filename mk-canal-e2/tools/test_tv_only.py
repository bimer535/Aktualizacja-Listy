"""TV release stays on the confirmed 0.4.0 account/DRM/player implementation."""
import io
from pathlib import Path
import sys
import tarfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'src/CanalE2Test'
sys.path.insert(0, str(SOURCE))
import player_runtime as runtime
import update_core as core
from test_epg import load_plugin_with_enigma_stubs


def data_files(body):
    archive = core.ar_members(body)
    with tarfile.open(fileobj=io.BytesIO(archive['data.tar.gz']), mode='r:gz') as tar:
        return {Path(m.name).name: tar.extractfile(m).read() for m in tar if m.isfile()}


def manifest():
    return ET.fromstring('''<MPD xmlns:cenc="urn:mpeg:cenc:2013"><Period>
      <AdaptationSet mimeType="video/mp4" codecs="avc1.64002a">
        <Representation id="uhd" height="2160" bandwidth="15000000">
          <ContentProtection cenc:default_KID="11111111-1111-1111-1111-111111111111"/></Representation>
        <Representation id="fullhd" height="1080" bandwidth="8000000">
          <ContentProtection cenc:default_KID="22222222-2222-2222-2222-222222222222"/></Representation>
        <Representation id="hd" height="720" bandwidth="4500000">
          <ContentProtection cenc:default_KID="33333333-3333-3333-3333-333333333333"/></Representation>
      </AdaptationSet><AdaptationSet mimeType="audio/mp4" lang="pl" codecs="mp4a.40.2">
        <Representation id="audio" bandwidth="128000"/></AdaptationSet></Period></MPD>''')


class TvOnlyTests(unittest.TestCase):
    def test_account_license_native_player_and_epg_match_original_ipk(self):
        baseline = data_files((ROOT / 'packages/MK_Canal_E2_0.4.0.ipk').read_bytes())
        changed = {'plugin.py', 'playback_worker.py', 'version.py', 'README.txt', 'account_worker.py'}
        active = {p.name for p in SOURCE.iterdir() if p.is_file()}
        self.assertEqual(active, set(baseline) | {'session_recover.py'})
        for name in baseline.keys() - changed:
            with self.subTest(file=name):
                self.assertEqual((SOURCE / name).read_bytes(), baseline[name])

    def test_entry_opens_channels_directly_without_vod_or_quality_dialog(self):
        plugin = load_plugin_with_enigma_stubs()
        session = SimpleNamespace(open=Mock())
        plugin.main(session)
        session.open.assert_called_once_with(plugin.CanalE2Channels)
        self.assertFalse(hasattr(plugin, 'CanalE2Quality'))
        self.assertFalse(hasattr(plugin, 'CanalE2Home'))
        self.assertNotIn('--vod', (SOURCE / 'playback_worker.py').read_text())
        self.assertNotIn('--choose-quality', (SOURCE / 'plugin.py').read_text())

    def test_auto_selects_highest_advertised_and_highest_granted_resolution(self):
        video, audio = runtime.select_tracks(manifest(), 4320)
        self.assertEqual(video['height'], 2160)
        self.assertEqual(audio['codec'], 'mp4a.40.2')
        options = runtime.licensed_video_options(manifest(), 4320, {'2' * 32, '3' * 32})
        self.assertEqual([item['height'] for item in options], [1080, 720])
        self.assertEqual(runtime.licensed_video_options(manifest(), 4320, {'3' * 32})[0]['height'], 720)


if __name__ == '__main__':
    unittest.main()
