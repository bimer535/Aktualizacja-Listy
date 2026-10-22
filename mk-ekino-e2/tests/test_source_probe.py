import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/MKEkinoE2'))
spec=importlib.util.spec_from_file_location('source_probe_test',ROOT/'tools/source_probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


class Response(io.BytesIO):
    code=206
    def __init__(self,data,kind):super().__init__(data);self.headers={'Content-Type':kind}
    def geturl(self):return 'https://cdn.example/private-video?token=secret'


class ProbeTests(unittest.TestCase):
    def test_report_features_exclude_source_urls_keys_and_page_contents(self):
        text='<iframe src="https://host.example/private?token=secret"></iframe><script>new Playerjs({file:"PRIVATE"})</script>'
        features=probe.page_features(text)
        self.assertEqual(features,['iframe','playerjs','file_field'])
        self.assertNotIn('secret',str(features));self.assertNotIn('PRIVATE',str(features))

    def test_media_probe_confirms_mp4_with_a_bounded_read_and_no_secret_headers(self):
        client=Mock();client.opener.open.return_value=Response(b'\0\0\0\x18ftyp'+b'x'*10000,'video/mp4')
        option={'url':probe.resolver.URL('https://cdn.example/private?token=secret',{'Referer':'https://host.example/','external_sub_tracks':[{'url':'PRIVATE'}]})}
        result=probe.media_check(client,option)
        self.assertEqual(result['status'],'media_reachable');self.assertEqual(result['bytes_read'],2048)
        self.assertNotIn('secret',str(result));self.assertNotIn('PRIVATE',str(result))
        request=client.opener.open.call_args.args[0]
        self.assertEqual(request.get_header('Range'),'bytes=0-2047')
        self.assertIsNone(request.get_header('External_sub_tracks'))

    def test_html_error_and_unresolved_hls_are_not_claimed_as_media(self):
        client=Mock();client.opener.open.return_value=Response(b'<html>error</html>','text/html')
        result=probe.media_check(client,{'url':'https://cdn.example/movie.mp4'})
        self.assertEqual(result['status'],'not_confirmed_media')
        client.getPage.return_value=(True,'#EXTM3U\nchild.m3u8\n')
        client.opener.open.return_value=Response(b'#EXTM3U\nsegment.ts\n','application/vnd.apple.mpegurl')
        result=probe.media_check(client,{'url':'https://cdn.example/master.m3u8'})
        self.assertEqual(result['status'],'not_confirmed_media')


if __name__=='__main__':unittest.main()
