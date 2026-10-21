"""Check that the comparison changes only User-Agent and preserves TLS/session handling."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/CanalE2Test'))
import canal_login_test as login
import login_browser


class Response(io.BytesIO):
    code = 200


class LoginBrowserTests(unittest.TestCase):
    def test_probe_changes_only_user_agent_and_does_not_add_credentials(self):
        seen = []
        def open_request(request, **kwargs):
            seen.append(request)
            self.assertEqual(kwargs['timeout'], 20)
            return Response(json.dumps({'authenticationToken': 'EXAMPLE-CODE', 'expires_in': 300}).encode())
        opener = Mock(open=Mock(side_effect=open_request))
        original = login.CanalLogin(opener=opener)
        alternate = login_browser.browser_client_type(login.CanalLogin)(opener=opener)
        original.create_code('local-test-device')
        alternate.create_code('local-test-device')
        first, second = seen
        a, b = dict(first.header_items()), dict(second.header_items())
        self.assertEqual(b.pop('User-agent'), login_browser.USER_AGENT)
        a.pop('User-agent')
        self.assertEqual(a, b)
        self.assertEqual(first.full_url, second.full_url)
        self.assertEqual(first.data, second.data)
        self.assertNotIn('Authorization', b)

    def test_http_failure_is_preserved_without_retry_or_session_change(self):
        failure = login.urllib.error.HTTPError(login.GENERATE_URL, 403, 'Forbidden', {},
                                             io.BytesIO(b'{"errorCode":9}'))
        opener = Mock(open=Mock(side_effect=failure))
        client = login_browser.browser_client_type(login.CanalLogin)(opener=opener)
        with self.assertRaises(login.LoginError) as caught:
            client.create_code('local-test-device')
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(caught.exception.error_code, 9)
        self.assertEqual(opener.open.call_count, 1)


if __name__ == '__main__':
    unittest.main()
