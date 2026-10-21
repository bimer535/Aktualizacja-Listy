#!/usr/bin/env python3
"""Catalogue fixtures match CANAL+ SSR observed on 2026-10-21; no account data."""
import ast
import base64
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

SOURCE = Path(__file__).resolve().parents[1] / 'src/CanalE2Test'
sys.path.insert(0, str(SOURCE))
import vod_data as v
import vod_api as api
import vod_worker
import canal_stream_test_v2 as stream
from test_epg import load_plugin_with_enigma_stubs, Container, Timer


def card(title='Film testowy', path='/pl/film/test/h/123_70026', cid='123_70026'):
    return {'contentID': cid, 'mediaData': {'image': {'alt': title}, 'linkerData': {
        'mainOnClick': {'displayName': title, 'path': path, 'displayTemplate': 'detailPage'}}}}


def ssr(*pages):
    return '<script>window.REACT_QUERY_STATE = ' + json.dumps({'queries': [
        {'state': {'data': p}} for p in pages]}, ensure_ascii=False) + ';</script>'


class CatalogueTests(unittest.TestCase):
    def test_catalogue_transport_uses_receiver_accepted_header_and_reports_refusal(self):
        # Model the receiver probe: app UA -> 403, standard browser UA -> 200.
        accepted = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/153.0.0.0 Safari/537.36')
        body = ssr({'currentPage': {'path': '/pl/film/'}, 'contents': [card()]}).encode()
        def open_request(request, **kwargs):
            self.assertFalse(request.has_header('Authorization'))
            self.assertFalse(request.has_header('Cookie'))
            if request.get_header('User-agent') != accepted:
                raise v.urllib.error.HTTPError(request.full_url, 403, 'Forbidden', {}, None)
            return io.BytesIO(body)
        opener = SimpleNamespace(open=open_request)
        with patch.object(v.urllib.request, 'build_opener', return_value=opener):
            page = v.load_page({'url': '/pl/film/'})
            self.assertEqual(page['items'][0]['title'], 'Film testowy')
            with patch.object(v, 'CATALOGUE_USER_AGENT', 'Mozilla/5.0 MK-Canal-E2'):
                with self.assertRaises(v.VodError) as caught:
                    v.fetch('/pl/film/')
        self.assertEqual(caught.exception.reason, 'vod_catalogue_http_error')
        self.assertEqual(caught.exception.details, {'http_status': 403})

    def test_parse_serialized_undefined_without_evaluating_javascript(self):
        page = 'window.__data = {"a":undefined,"b":"undefined","c":"x \\\" undefined"}; throw new Error();'
        self.assertEqual(v.script_value(page, '__data'), {'a': None, 'b': 'undefined', 'c': 'x " undefined'})
        with self.assertRaises(v.VodError):
            v.script_value('window.__data = executeSomething()', '__data')

    def test_modern_landing_category_and_more(self):
        row = {'title': 'Nowości', 'contents': [card(), card()], 'button': {
            'onClick': {'path': '/pl/theme/filmy/nowosci/'}}}
        result = v.load_page({'url': '/pl/film/'}, lambda _: ssr({'strates': [row]}))
        category = result['items'][0]['request']['inline']
        self.assertEqual(category['title'], 'Nowości')
        self.assertEqual(len(category['items']), 2)
        self.assertEqual(category['items'][0]['title'], 'Film testowy')
        self.assertEqual(category['items'][1]['request']['url'], '/pl/theme/filmy/nowosci/')

    def test_detail_uses_own_id_not_related_movie_and_does_not_open_upsell(self):
        film = {'currentPage': {'path': '/pl/film/test/h/123_70026'}, 'detail': {
            'contentID': '123_70026', 'title': 'Film', 'summary': {'text': 'Opis &amp; szczegóły'}},
            'actionLayout': {'primaryActions': [{'onClick': {'path': '/pl/upsell/'}}]}}
        related = {'currentPage': {'path': '/pl/film/test/h/123_70026/streaming/'}, 'contents': [card('Inny')]}
        page = v.load_page({'url': '/pl/film/test/h/123_70026'}, lambda _: ssr(related, film))
        self.assertEqual(page['description'], 'Opis & szczegóły')
        self.assertEqual([(i['kind'], i['id']) for i in page['items']], [('play', '123_70026')])

    def test_series_seasons_and_episodes_have_separate_navigation(self):
        detail = {'currentPage': {'displayTemplate': 'detailShow'}, 'detail': {'contentID': '123_70026', 'title': 'Serial'},
            'tabs': [{'displayTemplate': 'episodesList', 'displayName': 'Odcinki', 'path': '/pl/seriale/test/sezony/'}]}
        page = v.normalize_page(detail, '')
        self.assertEqual(page['items'][0]['kind'], 'folder')
        self.assertNotIn('play', [i['kind'] for i in page['items']])
        season = {'selector': [{'type': 'season', 'ariaLabel': 'Sezon 2', 'onClick': {'path': '/pl/seriale/test/sezon-2/'}}],
            'episodes': {'contents': [{'contentID': '456_70026', 'title': 'Odcinek 1', 'seasonNumber': 2,
            'episodeNumber': 1, 'summary': 'Opis odcinka'}, {'contentID': 'bad', 'title': 'Błąd'}]}}
        page = v.normalize_page(season, '')
        self.assertEqual(len(page['items']), 2)
        self.assertEqual(page['items'][1]['title'], 'S2 E1 · Odcinek 1')
        self.assertEqual(page['items'][1]['id'], '456_70026')

    def test_refreshing_inline_category_fetches_new_server_contents(self):
        seen = []
        def fetch(url):
            seen.append(url)
            return ssr({'strates': [{'title': 'Nowości', 'contents': [card('Nowy film')]}]})
        page = v.load_page({'url': '/pl/film/', 'category': 'Nowości'}, fetch)
        self.assertEqual(page['items'][0]['title'], 'Nowy film')
        self.assertEqual(len(seen), 1)

    def test_cursor_is_supplied_by_server_and_not_rewritten(self):
        url = v.HODOR + 'mycanalint/strateContent/public/1.json?after=YXJyOjEz&maxContentNumber=14'
        result = v.next_page({'hasNextPage': True, 'iterationType': 'id', 'idEnd': 'YXJyOjEz', 'URLPage': url})
        self.assertEqual(result['request']['url'], url)
        self.assertIsNone(v.next_page({'hasNextPage': False, 'URLPage': url}))

    def test_search_reads_current_public_configuration_and_encodes_query(self):
        seen = []
        def fetch(url):
            seen.append(url)
            if url == v.SITE + '/pl/':
                return 'window.__data = ' + json.dumps({'application': {'token': 'public-catalog-token',
                    'settings': {'searchUrl': 'search/discover/{cmsToken}/query/{searchKey}'}}})
            return json.dumps({'contents': [card()]})
        page = v.search('Film & serial', fetch)
        self.assertEqual(page['title'], 'Szukaj: Film & serial')
        self.assertTrue(seen[-1].endswith('/query/Film%20%26%20serial'))
        self.assertEqual(len(page['items']), 1)

    def test_catalogue_and_authenticated_api_reject_unexpected_hosts(self):
        for url in ['http://www.canalplus.com/pl/', 'https://evil.test/pl/',
                    'https://user:pass@hodor.canalplus.pro/api/v2/', 'https://127.0.0.1/api/v2/',
                    'https://www.canalplus.com:444/pl/']:
            with self.subTest(url=url), self.assertRaises(v.VodError):
                v.public_url(url)
        for url in ['http://secure-gen-hapi.canal-plus.com/x', '//evil.test/x',
                    'https://secure-gen-hapi.canal-plus.com:444/x']:
            with self.subTest(url=url), self.assertRaises(stream.StreamError):
                api.api_url(url)
        self.assertEqual(api.api_url('/conso/view'), api.HAPI + '/conso/view')

    def test_worker_errors_do_not_print_external_exception_or_read_account(self):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['vod_worker', '--request', '{}']), \
             patch.object(v, 'load_page', side_effect=RuntimeError('SECRET-TOKEN')), contextlib.redirect_stdout(output):
            self.assertEqual(vod_worker.main(), 1)
        self.assertNotIn('SECRET', output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['reason'], 'vod_catalogue_invalid_response')


class PlaybackApiTests(unittest.TestCase):
    def test_vod_uses_browser_header_and_retains_sanitized_playset_error(self):
        import urllib.error
        secret = 'DO-NOT-PRINT-ACCOUNT-TOKEN'
        body = json.dumps({'error': {'code': 43, 'message': 'Expired token ' + secret}, 'private': secret}).encode()
        calls = []
        def open_request(req, **kwargs):
            calls.append(req)
            self.assertEqual(req.get_header('User-agent'), v.CATALOGUE_USER_AGENT)
            raise urllib.error.HTTPError(req.full_url, 403, 'Forbidden', {}, io.BytesIO(body))
        client = api.VodApi({'passToken': secret}, '11111111', opener=SimpleNamespace(open=open_request))
        with self.assertRaisesRegex(stream.StreamError, 'vod_service_http_error'):
            client.playset('123_70026')
        self.assertEqual(len(calls), 1)
        self.assertEqual(client.diagnostic['service_codes'], {'code': 43})
        self.assertIn('expired_mentioned', client.diagnostic['message_hint_tags'])
        self.assertNotIn(secret, json.dumps(client.diagnostic))
        self.assertNotIn('Expired token', json.dumps(client.diagnostic))

    def test_non_json_licence_error_body_is_not_parsed_or_saved_in_diagnostic(self):
        import urllib.error
        response = io.BytesIO(b'PRIVATE LICENCE RESPONSE')
        client = api.VodApi({'passToken': 'PRIVATE'}, '11111111', opener=SimpleNamespace(
            open=lambda *args, **kwargs: (_ for _ in ()).throw(urllib.error.HTTPError('https://secure-gen-hapi.canal-plus.com/license', 403, 'Denied', {}, response))))
        client.stage = 'vod_licence'
        with self.assertRaises(stream.StreamError): client.request('/license')
        self.assertEqual(client.diagnostic['licence_http_error']['http_status'], 403)
        self.assertEqual(client.diagnostic['licence_http_error']['response_format'], 'non_json')
        self.assertNotIn('PRIVATE LICENCE RESPONSE', json.dumps(client.diagnostic))
        self.assertTrue(response.closed)

    def test_playset_view_media_contract_uses_subscription_session_and_no_purchase(self):
        client = api.VodApi({'passToken': 'PRIVATE-TOKEN'}, '11111111-1111-1111-1111-111111111111')
        option = {k: 'example' for k in ('comMode', 'contentId', 'distMode', 'distTechnology',
                    'drmType', 'functionalType', 'hash', 'idKey', 'quality')}
        option.update(drmType='DRM_COMMON_ENCRYPTION', quality='HD', distTechnology='DASH')
        calls = []
        def request(url, payload=None, method='GET', binary=False):
            calls.append((url, payload, method))
            if '/playset/' in url: return {'available': [option]}
            if url == '/conso/view': return {'@medias': '/media/1', '@licence': '/license/1'}
            return [{'files': [{'distribURL': 'https://cdn.example/film.mpd'}]}]
        mpd = ET.fromstring('<MPD><Period /></MPD>')
        with patch.object(client, 'request', side_effect=request), patch.object(stream, 'resolve_mpd', return_value=(mpd, 'https://cdn.example/film.mpd')):
            root, url, licence = client.resolve('123_70026')
        self.assertIs(root, mpd)
        self.assertEqual(licence, api.HAPI + '/license/1')
        self.assertEqual([c[2] for c in calls], ['GET', 'PUT', 'GET'])
        self.assertEqual(calls[1][1]['contentType'], option['distMode'])
        self.assertFalse(any('purchase' in c[0] for c in calls))

    def test_no_offer_does_not_start_view_or_request_license(self):
        client = api.VodApi({'passToken': 'PRIVATE'}, '11111111')
        with patch.object(client, 'request', return_value={'available': []}) as request:
            with self.assertRaisesRegex(stream.StreamError, 'vod_not_available_for_account'):
                client.resolve('123_70026')
        self.assertEqual(request.call_count, 1)

    def test_multiple_period_vod_is_rejected_instead_of_silently_truncated(self):
        client = api.VodApi({'passToken': 'PRIVATE'}, '11111111')
        option = dict.fromkeys(('comMode', 'contentId', 'distMode', 'distTechnology', 'functionalType', 'hash', 'idKey', 'quality'), 'x')
        option['drmType'] = 'DRM_COMMON_ENCRYPTION'
        with patch.object(client, 'request', side_effect=[{'available': [option]}, {'@medias': '/media', '@licence': '/license'},
                [{'files': [{'distribURL': 'https://cdn.example/film.mpd'}]}]]), \
                patch.object(stream, 'resolve_mpd', return_value=(ET.fromstring('<MPD><Period/><Period/></MPD>'), 'https://cdn.example/film.mpd')):
            with self.assertRaisesRegex(stream.StreamError, 'vod_multiple_periods_not_supported'):
                client.resolve('1_2')

    def test_hapi_license_decodes_xml_and_json_and_uses_base64_challenge(self):
        binary = b'\x08\x01\x12\x03abc'
        encoded = base64.b64encode(binary).decode()
        self.assertEqual(api.decode_licence(('<reply contentid="1">' + encoded + '</reply>').encode()), binary)
        self.assertEqual(api.decode_licence(json.dumps({'license': encoded}).encode()), binary)
        self.assertEqual(api.decode_licence(binary), binary)
        for raw in [b'', b'{"Status":-1}', b'<error>denied</error>']:
            with self.assertRaises(stream.StreamError): api.decode_licence(raw)
        client = api.VodApi({'passToken': 'PRIVATE'}, '11111111')
        with patch.object(client, 'request', return_value=binary) as request:
            self.assertEqual(client.licence('/license/1', b'challenge'), binary)
        args = request.call_args
        self.assertIn('drmType=DRM_WIDEVINE', args.args[0])
        self.assertEqual(args.args[1], base64.b64encode(b'challenge'))
        self.assertEqual(args.args[2], 'POST')

    def test_media_candidates_exclude_images_and_non_public_hosts(self):
        result = api.manifest_candidates([{'files': [{'distribURL': 'https://cdn.example/movie.ism'},
            {'distribURL': 'https://cdn.example/movie.mpd'}, {'distribURL': 'http://127.0.0.1/file.mpd'}],
            'URLImage': 'https://cdn.example/cover.jpg'}])
        self.assertEqual(result, ['https://cdn.example/movie.mpd', 'https://cdn.example/movie.ism/manifest(format=mpd-time-csf)'])


class WorkerRoutingTests(unittest.TestCase):
    def run_until_track_selection(self, vod, diagnostic=None):
        import playback_worker as worker
        import threading
        calls, emitted = [], []
        fake_api = SimpleNamespace(stage='vod_manifest', resolve=lambda cid: (calls.append(cid) or ('ROOT', 'https://cdn.example/film.mpd', '/license')), licence=lambda *args: b'')
        if diagnostic is not None:
            fake_api.stage, fake_api.diagnostic = 'vod_playset', diagnostic
            def fail_resolve(cid):
                raise stream.StreamError('vod_service_http_error', http_status=403)
            fake_api.resolve = fail_resolve
        saved = {'device_id': '11111111', 'authentication': {'passToken': 'PRIVATE-ACCOUNT-TOKEN'}}
        command = ['playback_worker', '--vod' if vod else '--channel', '123_70026' if vod else '12']
        import signal
        handlers = {n: signal.getsignal(n) for n in (signal.SIGINT, signal.SIGTERM)}
        try:
            with patch.object(sys, 'argv', command), patch.object(worker, 'STOP', threading.Event()), \
                 patch.object(worker.runtime, 'ensure_player', return_value=Path('/fake/bin/exteplayer3')), \
                 patch.object(worker.channels, 'load_json', return_value=saved), \
                 patch.object(worker.channels, 'get_client_ids', return_value={'UserKeyId': 'test-user', 'DeviceKeyId': 'test-device'}), \
                 patch.object(worker.channels, 'fetch_init', return_value={}) as live, \
                 patch.object(worker.channels, 'extract_outdata', return_value={}), \
                 patch.object(worker.channels, 'normalize_channels', return_value=[]), \
                 patch.object(worker.channels, 'atomic_private_json'), \
                 patch.object(worker.stream, 'select_channel', return_value={'name': 'Test HD'}), \
                 patch.object(worker.stream, 'entry_url', return_value='https://cdn.example/live.mpd'), \
                 patch.object(worker.stream, 'resolve_mpd', return_value=('ROOT', 'https://cdn.example/live.mpd')), \
                 patch.object(worker.runtime, 'select_tracks', side_effect=stream.StreamError('track_stage_reached')), \
                 patch.object(api, 'VodApi', return_value=fake_api) as vod_constructor, \
                 patch.object(worker, 'emit', side_effect=lambda stage, **kw: emitted.append({'stage': stage, **kw})):
                self.assertEqual(worker.main(), 1)
            self.assertNotIn('PRIVATE-ACCOUNT-TOKEN', json.dumps(emitted))
            self.assertEqual(emitted[-1]['reason'], 'vod_service_http_error' if diagnostic is not None else 'track_stage_reached')
            return calls, live.call_count, vod_constructor.call_count, emitted
        finally:
            for number, handler in handlers.items(): signal.signal(number, handler)

    def test_vod_does_not_call_live_channel_or_license_endpoint(self):
        calls, live_calls, vod_calls, emitted = self.run_until_track_selection(True)
        self.assertEqual(calls, ['123_70026'])
        self.assertEqual(live_calls, 0)
        self.assertEqual(vod_calls, 1)
        self.assertEqual(emitted[-1]['vod_step'], 'vod_manifest')

    def test_vod_http_diagnostic_is_in_normal_playback_report_events(self):
        diagnostic = {'http_status': 403, 'response_format': 'json', 'service_codes': {'code': 43}}
        _, _, _, events = self.run_until_track_selection(True, diagnostic)
        self.assertEqual(events[-1]['vod_http_diagnostic'], diagnostic)
        self.assertEqual(events[-1]['vod_step'], 'vod_playset')

    def test_live_keeps_existing_path_and_does_not_create_vod_session(self):
        calls, live_calls, vod_calls, emitted = self.run_until_track_selection(False)
        self.assertEqual(live_calls, 1)
        self.assertEqual(vod_calls, 0)
        self.assertNotIn('vod_step', emitted[-1])


class GuiTests(unittest.TestCase):
    def load_ui(self):
        plugin = load_plugin_with_enigma_stubs()
        names = {'Components.ActionMap': ('ActionMap', plugin.ActionMap),
            'Components.Label': ('Label', plugin.Label), 'Components.MenuList': ('MenuList', plugin.MenuList),
            'Components.ScrollLabel': ('ScrollLabel', plugin.ScrollLabel), 'Screens.Screen': ('Screen', plugin.Screen)}
        modules = {}
        for name, (key, value) in names.items():
            modules[name] = ModuleType(name); setattr(modules[name], key, value)
        modules['enigma'] = SimpleNamespace(eTimer=Timer, eConsoleAppContainer=Container)
        package = ModuleType('vod_gui_test'); package.__path__ = [str(SOURCE)]
        modules['vod_gui_test'] = package
        spec = importlib.util.spec_from_file_location('vod_gui_test.vod_ui', SOURCE / 'vod_ui.py')
        ui = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules): spec.loader.exec_module(ui)
        return ui, plugin

    def test_async_utf8_results_history_back_and_cancellation(self):
        ui, _ = self.load_ui()
        screen = ui.CanalVodBrowser(SimpleNamespace(), {'url': '/pl/film/'})
        screen.reload()
        body = json.dumps({'stage': 'vod_loaded', 'page': {'title': 'Żółty', 'items': [
            {'title': 'Sezony', 'kind': 'folder', 'request': {'inline': {'title': 'Sezon 1', 'items': []}}}]}}, ensure_ascii=False).encode() + b'\n'
        for byte in body: screen.data(bytes([byte]))
        screen.finished(0)
        self.assertEqual(screen['title'].text, 'Żółty')
        screen.select()
        self.assertEqual(screen['title'].text, 'Sezon 1')
        screen.back()
        self.assertEqual(screen['title'].text, 'Żółty')
        screen.reload(); process = screen.container
        screen.cleanup()
        self.assertTrue(process.interrupted)
        screen.data(body)
        self.assertEqual(process.dataAvail, [])

    def test_catalogue_error_shows_http_status_and_survives_worker_exit(self):
        ui, _ = self.load_ui()
        screen = ui.CanalVodBrowser(SimpleNamespace(), {'url': '/pl/film/'})
        screen.reload()
        screen.data(b'{"stage":"error","reason":"vod_catalogue_http_error","http_status":403}\n')
        screen.finished(1)
        self.assertIn('HTTP 403', screen['status'].text)
        screen.cleanup()

    def test_vod_player_disables_epg_and_waits_for_native_pause_confirmation(self):
        _, plugin = self.load_ui()
        session = SimpleNamespace(nav=SimpleNamespace(getCurrentlyPlayingServiceReference=lambda: None))
        player = plugin.CanalE2Player(session, '123_70026', 'Film', True, 'Opis filmu')
        self.assertIsNone(player.epg_loader.channel)
        sent = []
        player.container = SimpleNamespace(write=sent.append)
        player.running = True
        player.on_data(b'{"stage":"player_running"}\n')
        self.assertIn('VOD', player['status'].text)
        player.pause_resume()
        self.assertEqual(sent, [b'pause\n'])
        self.assertFalse(player.paused)
        player.on_data(b'{"stage":"vod_paused"}\n')
        self.assertTrue(player.paused)
        player.pause_resume()
        player.control('seek_forward')
        self.assertEqual(sent[-2:], [b'resume\n', b'seek_forward\n'])
        player.on_data(b'{"stage":"vod_resumed"}\n')
        self.assertFalse(player.paused)
        player.container = None; player.cleanup()

    def test_vod_skin_geometry_fits(self):
        for cls in ast.parse((SOURCE / 'vod_ui.py').read_text()).body:
            if not isinstance(cls, ast.ClassDef): continue
            for stmt in cls.body:
                if isinstance(stmt, ast.Assign) and any(isinstance(x, ast.Name) and x.id == 'skin' for x in stmt.targets):
                    root = ET.fromstring(ast.literal_eval(stmt.value))
                    width, height = map(int, root.attrib['size'].split(','))
                    for widget in root:
                        x, y = map(int, widget.attrib['position'].split(','))
                        w, h = map(int, widget.attrib['size'].split(','))
                        self.assertLessEqual(x+w, width); self.assertLessEqual(y+h, height)


if __name__ == '__main__':
    unittest.main()
