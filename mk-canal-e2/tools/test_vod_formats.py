"""Real format selection rather than deriving DASH from every Smooth source."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/CanalE2Test'))
import canal_stream_test_v2 as stream
import vod_api as api


def offer(drm, delivery):
    value = dict.fromkeys(('comMode', 'contentId', 'distMode', 'functionalType',
                          'hash', 'idKey', 'quality'), 'PRIVATE-OFFER')
    value.update(drmType=drm, distTechnology=delivery, quality='HD')
    return value


class VodFormatTests(unittest.TestCase):
    def test_embedded_media_uses_own_licence_and_preserves_complete_offer(self):
        selected = dict(offer('DRM_WIDEVINE', 'DASH'), serviceField='SERVER-DESCRIPTOR')
        client = api.VodApi({'passToken': 'PRIVATE'}, '11111111')
        client.request = Mock(side_effect=[{'available': [selected]}, {
            '@licence': '/view/licence', 'medias': [
                {'type': 'feature', '@licence': '/media/licence?x=1&x=2', 'files': [
                    {'type': 'video', 'mimeType': 'application/dash+xml', 'distribURL': 'https://cdn.example/movie'}]}]}])
        with patch.object(stream, 'resolve_mpd', return_value=(ET.fromstring('<MPD><Period/></MPD>'),
                                                             'https://cdn.example/movie')):
            _, _, licence = client.resolve('1_2')
        self.assertEqual(licence, api.HAPI + '/media/licence?x=1&x=2')
        self.assertEqual(client.request.call_count, 2)
        self.assertEqual(client.request.call_args.args, ('/conso/view?include=medias', selected, 'PUT'))
        self.assertTrue(client.diagnostic['view_includes_medias'])
        self.assertEqual(client.diagnostic['licence_reference_source'], 'media')

    def test_multiple_media_licences_never_become_detached_from_their_manifest(self):
        medias = [{'@licence': '/license/one', 'files': [{'distribURL': 'https://cdn.example/a.ism'}]},
                  {'@licence': '/license/two', 'files': [{'distribURL': 'https://cdn.example/b.mpd'}]}]
        result = api.manifest_licence_pairs(medias, api.HAPI + '/view')
        self.assertEqual(result[0], ('https://cdn.example/b.mpd', api.HAPI + '/license/two', 'media'))
        self.assertEqual(result[1][1], api.HAPI + '/license/one')
        with self.assertRaisesRegex(stream.StreamError, 'vod_invalid_api_reference'):
            api.manifest_licence_pairs([{'@licence': 'https://other.example/steal',
                                        'files': [{'distribURL': 'https://cdn.example/b.mpd'}]}])

    def test_widevine_dash_is_selected_instead_of_common_encryption_smooth(self):
        smooth = offer('DRM_COMMON_ENCRYPTION', 'SMOOTHSTREAMING')
        dash = offer('DRM_WIDEVINE', 'DASH')
        client = api.VodApi({'passToken': 'PRIVATE-TOKEN'}, '11111111')
        client.request = Mock(side_effect=[{'available': [smooth, dash]},
            {'@medias': '/medias', '@licence': '/licence'},
            [{'files': [{'mimeType': 'application/dash+xml',
                         'distribURL': 'https://cdn.example/delivery?token=PRIVATE-URL'}]}]])
        root = ET.fromstring('<MPD><Period /></MPD>')
        with patch.object(stream, 'resolve_mpd', return_value=(root, 'https://cdn.example/final.mpd')) as resolve:
            client.resolve('1_2')
        self.assertEqual(client.request.call_args_list[1].args[1]['drmType'], 'DRM_WIDEVINE')
        self.assertEqual(resolve.call_args.args[1], 'https://cdn.example/delivery?token=PRIVATE-URL')
        self.assertEqual(client.diagnostic['selected_drm_profile'], 'widevine')
        self.assertTrue(client.diagnostic['selected_delivery_is_dash'])
        encoded = json.dumps(client.diagnostic)
        for secret in ('PRIVATE', 'cdn.example', 'hash', 'contentId'):
            self.assertNotIn(secret, encoded)

    def test_mime_typed_dash_keeps_signed_url_exact_and_takes_precedence(self):
        target = 'https://cdn.example/delivery?token=PRIVATE%2B%2F&x=1&x=2'
        medias = [{'files': [{'distribURL': 'https://cdn.example/movie.ism'},
                             {'mimeType': 'application/dash+xml; charset=utf-8', 'distribURL': target}]}]
        self.assertEqual(api.manifest_candidates(medias)[0], target)

    def test_available_formats_are_fixed_labels_and_counts_only(self):
        values = [offer('DRM_WIDEVINE', 'DASH'), offer('DRM_WIDEVINE', 'DASH'),
                  offer('PRIVATE-DRM', 'PRIVATE-DELIVERY'), None]
        result = api.available_format_summary(values)
        self.assertIn({'drm': 'widevine', 'delivery': 'dash', 'count': 2}, result)
        self.assertIn({'drm': 'other', 'delivery': 'other', 'count': 1}, result)
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_widevine_is_preferred_when_delivery_enum_does_not_name_dash(self):
        common = offer('DRM_COMMON_ENCRYPTION', 'HTTPSTREAMING')
        widevine = offer('DRM_WIDEVINE', 'HTTPSTREAMING')
        client = api.VodApi({'passToken': 'PRIVATE'}, '11111111')
        client.request = Mock(side_effect=[{'available': [common, widevine]},
            {'@medias': '/media', '@licence': '/licence'},
            [{'files': [{'distribURL': 'https://cdn.example/movie.mpd'}]}]])
        with patch.object(stream, 'resolve_mpd', return_value=(ET.fromstring('<MPD><Period/></MPD>'),
                                                             'https://cdn.example/movie.mpd')):
            client.resolve('1_2')
        self.assertEqual(client.request.call_args_list[1].args[1]['drmType'], 'DRM_WIDEVINE')

    def test_original_smooth_200_is_reported_without_claiming_playback_or_requesting_licence(self):
        media_http = Mock()
        media_http.read.return_value = (b'<SmoothStreamingMedia><StreamIndex Type="video">'
            b'<QualityLevel MaxHeight="1080" CodecPrivateData="PRIVATE"/>'
            b'</StreamIndex></SmoothStreamingMedia>', 'https://cdn.example/movie.ism/manifest')
        media_http.last_response_metadata = {'http_status': 200, 'response_content_type': 'text/xml'}
        client = api.VodApi({'passToken': 'PRIVATE-TOKEN'}, '11111111', media_http=media_http)
        client.request = Mock(side_effect=[{'available': [offer('DRM_COMMON_ENCRYPTION', 'SMOOTHSTREAMING')]},
            {'@medias': '/media', '@licence': '/licence'},
            [{'files': [{'distribURL': 'https://cdn.example/movie.ism?token=PRIVATE%2B'}]}]])
        with patch.object(stream, 'resolve_mpd', side_effect=stream.StreamError('http_error', http_status=503)):
            with self.assertRaisesRegex(stream.StreamError, 'vod_smooth_streaming_not_supported'):
                client.resolve('1_2')
        media_http.read.assert_called_once_with('https://cdn.example/movie.ism/manifest?token=PRIVATE%2B')
        self.assertEqual(client.request.call_count, 3)  # no licence or purchase request
        self.assertEqual(client.diagnostic['source_manifest_check']['video_heights'], [1080])
        self.assertNotIn('PRIVATE', json.dumps(client.diagnostic))


if __name__ == '__main__':
    unittest.main()
