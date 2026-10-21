#!/usr/bin/env python3
"""Read-only public catalogue connectivity check; no account files or credentials."""
import ast
import concurrent.futures
import json
from pathlib import Path
import ssl
import urllib.error
import urllib.parse
import urllib.request

SITE = 'https://www.canalplus.com'
APP_UA = 'Mozilla/5.0 MK-Canal-E2'
BROWSER_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
              'AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/153.0.0.0 Safari/537.36')
LIMIT = 4 * 1024 * 1024
CHECKS = [('plugin_filmy', '/pl/film/', APP_UA),
          ('standard_filmy', '/pl/film/', BROWSER_UA),
          ('standard_seriale', '/pl/seriale/', BROWSER_UA)]


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(urllib.parse.urljoin(req.full_url, newurl))
        if (parsed.scheme != 'https' or parsed.hostname != 'www.canalplus.com'
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise ValueError('unexpected_redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def check(entry, opener=None):
    name, path, agent = entry
    headers = {'User-Agent': agent, 'Accept-Language': 'pl-PL,pl;q=0.9',
               'Accept-Encoding': 'identity', 'Origin': SITE,
               'Accept': 'text/html,application/json'}
    request = urllib.request.Request(SITE + path, headers=headers)
    opener = opener or urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()), OfficialRedirect())
    result = {'test': name}
    try:
        try:
            response = opener.open(request, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read(LIMIT + 1)
            result.update(http_status=response.code,
                          content_type=response.headers.get_content_type(),
                          catalogue_present=b'window.REACT_QUERY_STATE' in body,
                          bytes_read=min(len(body), LIMIT), truncated=len(body) > LIMIT)
    except Exception as error:
        # Do not print raw exceptions, headers, cookies or server response text.
        result['error'] = ('connection_or_tls_error' if isinstance(error, (urllib.error.URLError, OSError))
                           else 'unexpected_redirect' if isinstance(error, ValueError)
                           else 'probe_failed')
    return result


def installed_version():
    path = Path('/usr/lib/enigma2/python/Plugins/Extensions/CanalE2Test/version.py')
    try:
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.Assign) and any(isinstance(n, ast.Name) and n.id == 'APP_VERSION' for n in node.targets):
                value = ast.literal_eval(node.value)
                return value if isinstance(value, str) and len(value) < 24 else 'unknown'
    except (OSError, SyntaxError, ValueError):
        pass
    return 'unknown'


def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(check, CHECKS))
    print(json.dumps({'probe_version': 1, 'installed_version': installed_version(),
                      'account_files_read': False, 'configuration_changed': False,
                      'checks': results}, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
