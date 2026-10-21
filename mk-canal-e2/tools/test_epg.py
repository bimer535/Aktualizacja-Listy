#!/usr/bin/env python3
"""Now/next, cache, clock boundaries and asynchronous Enigma2 UI tests."""
import copy
import datetime
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import ast

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/CanalE2Test"
sys.path.insert(0, str(SOURCE))
import epg_data as epg

NOW = epg.iso_timestamp("2026-10-21T03:00:00Z")


def feed():
    # Same fields and millisecond duration format as the receiver probe.
    def event(title, start, duration, **extra):
        return {"title": title, "subTitle": "Film, Polska", "genre": 1,
                "timecodes": [{"start": start, "duration": duration, "type": 0}], **extra}
    return {"channels": [{"id": 12, "name": "Test HD", "events": [
        event("Wcześniejsza", "2026-10-21T01:00:00Z", 3600000),
        event("Aktualna audycja", "2026-10-21T02:56:00.000Z", 8640000),
        event("Następna audycja", "2026-10-21T05:20:00.000Z", 8760000),
        event("Późniejsza", "2026-10-21T07:46:00Z", 3600000)]}]}


class MetadataTests(unittest.TestCase):
    def test_receiver_schema_selects_exactly_current_and_next(self):
        value = epg.normalize_feed(feed(), NOW)
        events = value["channels"]["12"]["programmes"]
        self.assertEqual([p["title"] for p in events], ["Aktualna audycja", "Następna audycja"])
        self.assertEqual(events[0]["end"], epg.iso_timestamp("2026-10-21T05:20:00Z"))
        self.assertEqual(events[1]["end"], epg.iso_timestamp("2026-10-21T07:46:00Z"))
        self.assertEqual(events[0]["description"], "")
        self.assertEqual(events[0]["subtitle"], "Film, Polska")

    def test_boundary_gap_and_end_never_show_expired_programme_as_current(self):
        events = epg.normalize_events(feed()["channels"][0]["events"])
        at_end = epg.choose_pair(events, epg.iso_timestamp("2026-10-21T05:20:00Z"))
        self.assertEqual(at_end["current"]["title"], "Następna audycja")
        gap = epg.choose_pair(events, epg.iso_timestamp("2026-10-21T02:30:00Z"))
        self.assertIsNone(gap["current"])
        self.assertEqual(gap["next"]["title"], "Aktualna audycja")
        self.assertEqual(epg.choose_pair(events, NOW + 86400), {"current": None, "next": None})

    def test_timezones_and_missing_or_malformed_metadata(self):
        self.assertEqual(epg.iso_timestamp("2026-10-21T05:00:00+02:00"), NOW)
        self.assertIsNone(epg.iso_timestamp("2026-10-21T05:00:00"))
        raw = feed()["channels"][0]["events"][1]
        invalid = [None, {}, dict(raw, title=None), dict(raw, timecodes=[]),
                   dict(raw, timecodes=[{"start": "garbage", "duration": 1000}]),
                   dict(raw, timecodes=[{"start": "2026-10-21T03:00:00Z", "duration": True}])]
        self.assertEqual(epg.normalize_events(invalid), [])
        raw["description"] = "Pełny <b>opis</b> &amp; szczegóły."
        self.assertEqual(epg.normalize_events([raw])[0]["description"], "Pełny opis & szczegóły.")
        self.assertEqual(epg.normalize_events([raw, raw]), epg.normalize_events([raw]))

    def test_cache_reuses_request_across_channels_and_refreshes_at_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "epg.json"
            with patch.object(epg, "fetch_feed", side_effect=AssertionError("unexpected network")):
                calls = []
                def fetch():
                    calls.append(True)
                    return feed()
                first = epg.get_pair("12", path, fetch, lambda: NOW)
                second = epg.get_pair("12", path, fetch, lambda: NOW + 30)
                absent = epg.get_pair("999", path, fetch, lambda: NOW + 30)
                self.assertEqual(first["current"], second["current"])
                self.assertEqual(len(calls), 1)
                self.assertIsNone(absent["current"])
                self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
                self.assertEqual(len(epg.read_cache(path)["channels"]["12"]["programmes"]), 2)
                end = first["current"]["end"]
                result = epg.get_pair("12", path, fetch, lambda: end)
                self.assertEqual(result["current"]["title"], "Następna audycja")
                self.assertEqual(result["next"]["title"], "Późniejsza")
                self.assertEqual(len(calls), 2)

    def test_network_failure_keeps_only_time_valid_cached_programmes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "epg.json"
            epg.get_pair("12", path, feed, lambda: NOW)
            def fail():
                raise epg.EpgError("epg_http_403")
            value = epg.get_pair("12", path, fail, lambda: NOW + 121)
            self.assertTrue(value["cached"])
            self.assertEqual(value["current"]["title"], "Aktualna audycja")
            with self.assertRaisesRegex(epg.EpgError, "epg_http_403"):
                epg.get_pair("12", path, fail, lambda: NOW + 901)

    def test_invalid_cache_and_future_clock_are_refetched(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "epg.json"
            path.write_text('{"schema":1,"fetched_at":0,"channels":{"12":{}}}')
            self.assertIsNone(epg.read_cache(path))
            epg.get_pair("12", path, feed, lambda: NOW + 60)
            calls = []
            result = epg.get_pair("12", path, lambda: (calls.append(True) or feed()), lambda: NOW)
            self.assertEqual(len(calls), 1)
            self.assertIsNotNone(result["current"])


class Timer:
    def __init__(self):
        self.callback, self.active = [], False
    def start(self, *args):
        self.active = True
    def stop(self):
        self.active = False


class Container:
    instances = []
    def __init__(self):
        self.dataAvail, self.appClosed = [], []
        self.interrupted = False
        self.written = []
        self.instances.append(self)
    def execute(self, *args):
        self.arguments = args
        return 0
    def sendCtrlC(self):
        self.interrupted = True
    def write(self, data, length=None):
        # Match the OpenATV Python binding, not subprocess.stdin's byte API.
        if not isinstance(data, str):
            raise TypeError('1st arg must be a string, optionally 2nd arg can be the string length')
        if length is not None and length != len(data):
            raise ValueError('incorrect command length')
        self.written.append(data)


def load_plugin_with_enigma_stubs():
    class Screen(dict):
        def __init__(self, session):
            super().__init__()
            self.session = session
            self.onShow, self.onHide, self.onClose, self.onFirstExecBegin = [], [], [], []
        def close(self, *args):
            pass
    class Label:
        def __init__(self, text=""):
            self.text = text
        def setText(self, value):
            self.text = value
        def show(self):
            pass
        def hide(self):
            pass
        def pageUp(self):
            pass
        def pageDown(self):
            pass
        def setRange(self, value):
            self.range = value
        def setValue(self, value):
            self.value = value
    class MenuList:
        def __init__(self, items):
            self.items, self.onSelectionChanged = items, []
            self.index = 0
        def setList(self, items):
            self.items = items
            for callback in self.onSelectionChanged:
                callback()
        def getCurrent(self):
            return self.items[self.index] if self.items else None
        def up(self):
            self.index = max(0, self.index - 1)
        def down(self):
            self.index = min(len(self.items) - 1, self.index + 1)
        def pageUp(self):
            self.index = max(0, self.index - 10)
        def pageDown(self):
            self.index = min(len(self.items) - 1, self.index + 10)
    class ActionMap:
        def __init__(self, contexts, actions, *args):
            self.actions = actions
    class Descriptor:
        WHERE_PLUGINMENU = 1
        def __init__(self, **kwargs):
            self.values = kwargs
    modules = {}
    components = {"Components.ActionMap": ("ActionMap", ActionMap),
        "Components.Label": ("Label", Label), "Components.MenuList": ("MenuList", MenuList),
        "Components.ProgressBar": ("ProgressBar", Label), "Components.ScrollLabel": ("ScrollLabel", Label),
        "Screens.Screen": ("Screen", Screen), "Screens.MessageBox": ("MessageBox", Label),
        "Plugins.Plugin": ("PluginDescriptor", Descriptor)}
    for name, (attribute, value) in components.items():
        module = ModuleType(name)
        setattr(module, attribute, value)
        modules[name] = module
    fake = ModuleType("enigma")
    fake.eTimer, fake.eConsoleAppContainer = Timer, Container
    modules["enigma"] = fake
    package = ModuleType("gui_epg_test")
    package.__path__ = [str(SOURCE)]
    modules[package.__name__] = package
    spec = importlib.util.spec_from_file_location("gui_epg_test.plugin", SOURCE / "plugin.py")
    plugin = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(plugin)
    return plugin


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake = ModuleType("enigma")
        fake.eTimer, fake.eConsoleAppContainer = Timer, Container
        spec = importlib.util.spec_from_file_location("test_epg_ui_module", SOURCE / "epg_ui.py")
        cls.ui = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"enigma": fake}):
            spec.loader.exec_module(cls.ui)

    def test_fast_selection_discards_old_channel_results_and_coalesces_requests(self):
        events = []
        loader = self.ui.EpgLoader(events.append)
        loader.request("12")
        loader.resume()
        loader.start()
        old = loader.container
        loader.request("13")
        loader.start()
        self.assertIs(loader.container, old)
        loader.data(b'{"stage":"epg_loaded","channel_id":"12"}\n')
        self.assertEqual(events, [])
        loader.finished(0)
        loader.start()
        self.assertEqual(loader.container.arguments[-1], "13")
        body = json.dumps({"stage": "epg_loaded", "channel_id": "13", "title": "Żółty"}, ensure_ascii=False).encode() + b"\n"
        for byte in body:
            loader.data(bytes([byte]))
        self.assertEqual(events[0]["title"], "Żółty")
        loader.finished(0)
        self.assertTrue(loader.refresh_timer.active)
        loader.close()

    def test_hiding_or_closing_screen_stops_worker_and_callbacks(self):
        loader = self.ui.EpgLoader(lambda event: self.fail("Callback after hide"))
        loader.request("12")
        loader.resume()
        loader.start()
        container = loader.container
        loader.pause()
        self.assertTrue(container.interrupted)
        self.assertEqual(container.dataAvail, [])
        self.assertEqual(container.appClosed, [])
        self.assertFalse(loader.refresh_timer.active)
        loader.data(b'{"stage":"epg_loaded","channel_id":"12"}\n')
        loader.close()
        loader.resume()
        loader.start()
        self.assertFalse(loader.running)

    def test_skin_widgets_fit_and_channel_header_does_not_overlap_epg(self):
        tree = ast.parse((SOURCE / "plugin.py").read_text())
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef):
                continue
            for statement in cls.body:
                if not isinstance(statement, ast.Assign):
                    continue
                if not any(isinstance(t, ast.Name) and t.id == "skin" for t in statement.targets):
                    continue
                skin = ET.fromstring(ast.literal_eval(statement.value))
                width, height = map(int, skin.attrib["size"].split(","))
                for widget in skin:
                    if "position" in widget.attrib and "size" in widget.attrib:
                        x, y = map(int, widget.attrib["position"].split(","))
                        w, h = map(int, widget.attrib["size"].split(","))
                        self.assertLessEqual(x + w, width)
                        self.assertLessEqual(y + h, height)

    def test_channel_screen_and_info_show_original_metadata_and_keep_play_action(self):
        plugin = load_plugin_with_enigma_stubs()
        opened = []
        session = SimpleNamespace(open=lambda *args: opened.append(args))
        channels = {"channels": [{"authorized": True, "name": "Test HD", "epg_id": "12"}]}
        with patch.object(plugin.Path, "read_text", return_value=json.dumps(channels)):
            screen = plugin.CanalE2Channels(session)
        data = {"stage": "epg_loaded", "channel_id": "12", **epg.choose_pair(
            epg.normalize_events(feed()["channels"][0]["events"]), NOW)}
        screen.epg_received(data)
        self.assertIn("Aktualna audycja", screen["now_title"].text)
        self.assertEqual(screen["now_details"].text, "Film, Polska")
        self.assertIn("Następna audycja", screen["next_title"].text)
        screen["actions"].actions["info"]()
        info = plugin.CanalE2NowNext(session, *opened[-1][1:])
        self.assertIn("Film, Polska", info["body"].text)
        screen["actions"].actions["ok"]()
        self.assertEqual(opened[-1], (plugin.CanalE2Player, "12", "Test HD", False, "", [("Test HD", "12")]))
        screen.cleanup_epg()

    def test_player_info_does_not_override_playback_error_or_stop(self):
        plugin = load_plugin_with_enigma_stubs()
        opened = []
        session = SimpleNamespace(open=lambda *args: opened.append(args),
            nav=SimpleNamespace(getCurrentlyPlayingServiceReference=lambda: None))
        player = plugin.CanalE2Player(session, "12", "Test HD")
        player.on_data(b'{"stage":"player_running"}\n')
        data = {"stage": "epg_loaded", "channel_id": "12", **epg.choose_pair(
            epg.normalize_events(feed()["channels"][0]["events"]), NOW)}
        player.epg_received(data)
        self.assertIn("Aktualna audycja", player["status"].text)
        player.show_programmes()
        self.assertEqual(opened[-1][0], plugin.CanalE2NowNext)
        player.on_data(b'{"stage":"error","reason":"test_error"}\n')
        player.epg_received(data)
        self.assertIn("test_error", player["status"].text)
        player.stop()
        player.cleanup()
        self.assertTrue(player.epg_loader.closed)


if __name__ == "__main__":
    unittest.main()
