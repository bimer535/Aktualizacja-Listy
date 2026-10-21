#!/usr/bin/env python3
"""One controlled login-header comparison using the installed CANAL+ client.

--probe checks code generation without showing the code or changing a session.
--new-login invokes the existing pairing flow; the owner approves its code.
Only User-Agent changes. No receiver/plugin files are modified by this helper;
the existing login client saves a session only after successful authentication.
"""
from pathlib import Path
import sys

PLUGIN = Path('/usr/lib/enigma2/python/Plugins/Extensions/CanalE2Test')
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
              'AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/153.0.0.0 Safari/537.36')


class BrowserHeaders:
    def __init__(self, opener):
        self.opener = opener

    def open(self, request, **kwargs):
        request.add_header('User-Agent', USER_AGENT)
        return self.opener.open(request, **kwargs)


def browser_client_type(original):
    class BrowserLogin(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.opener = BrowserHeaders(self.opener)
    return BrowserLogin


def main():
    if not (PLUGIN / 'canal_login_test.py').is_file():
        print('Nie znaleziono zainstalowanej wtyczki MK Canal+ E2.')
        return 2
    sys.path.insert(0, str(PLUGIN))
    import canal_login_test as login
    original = login.CanalLogin
    login.CanalLogin = browser_client_type(original)
    try:
        return login.main()
    finally:
        login.CanalLogin = original


if __name__ == '__main__':
    raise SystemExit(main())
