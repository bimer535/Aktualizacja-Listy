"""Small remote-control VOD browser, independent of Kodi and E2iPlayer."""
import codecs
import json
from pathlib import Path
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.ScrollLabel import ScrollLabel
from Screens.Screen import Screen
from enigma import eConsoleAppContainer, eTimer

ERRORS = {
    'vod_catalogue_http_error': 'Serwer katalogu odmówił połączenia. Spróbuj ponownie później.',
    'vod_catalogue_connection_error': 'Nie można połączyć się z katalogiem CANAL+.',
    'vod_catalogue_format_changed': 'Nie rozpoznano danych katalogu CANAL+.',
    'vod_search_configuration_missing': 'Wyszukiwanie jest chwilowo niedostępne.',
}


class CanalVodDescription(Screen):
    skin = '''<screen name="CanalVodDescription" position="center,center" size="1000,580" title="MK Canal+ E2 — opis">
      <widget name="body" position="30,25" size="940,465" font="Regular;25" />
      <widget name="hint" position="30,510" size="940,40" font="Regular;21" />
    </screen>'''

    def __init__(self, session, title, description):
        Screen.__init__(self, session)
        self['body'] = ScrollLabel(title + '\n\n' + (description or 'Brak opisu w danych CANAL+.'))
        self['hint'] = Label('↑/↓: przewijanie  ·  OK / EXIT: Wróć')
        self['actions'] = ActionMap(['OkCancelActions', 'DirectionActions'], {
            'ok': self.close, 'cancel': self.close,
            'up': self['body'].pageUp, 'down': self['body'].pageDown}, -2)


class CanalVodBrowser(Screen):
    skin = '''<screen name="CanalVodBrowser" position="center,center" size="1000,640" title="MK Canal+ E2 — VOD">
      <widget name="title" position="25,20" size="950,45" font="Regular;30" />
      <widget name="items" position="25,90" size="520,405" scrollbarMode="showOnDemand" />
      <widget name="description" position="570,90" size="405,405" font="Regular;23" />
      <widget name="status" position="25,512" size="950,54" font="Regular;20" foregroundColor="#c8c8c8" />
      <widget name="key_red" position="25,582" size="220,36" font="Regular;22" halign="center" backgroundColor="#a42c35" />
      <widget name="key_green" position="265,582" size="220,36" font="Regular;22" halign="center" backgroundColor="#177443" />
      <widget name="key_yellow" position="505,582" size="220,36" font="Regular;22" halign="center" foregroundColor="black" backgroundColor="#e3bc38" />
      <widget name="key_blue" position="745,582" size="230,36" font="Regular;22" halign="center" backgroundColor="#2363ba" />
    </screen>'''

    def __init__(self, session, request=None, query=None):
        Screen.__init__(self, session)
        self['title'] = Label('CANAL+ VOD')
        self['items'] = MenuList([])
        self['description'] = ScrollLabel('')
        self['status'] = Label('Pobieranie katalogu...')
        for key, label in [('red', 'Wróć'), ('green', 'Szukaj'), ('yellow', 'Odśwież'), ('blue', 'Opis')]:
            self['key_' + key] = Label(label)
        self['actions'] = ActionMap(['OkCancelActions', 'ColorActions', 'InfoActions'], {
            'ok': self.select, 'cancel': self.back, 'red': self.back, 'green': self.search,
            'yellow': lambda: self.reload(force=True), 'blue': self.details, 'info': self.details}, -2)
        self['items'].onSelectionChanged.append(self.selection_changed)
        self.request = {'search': query} if query is not None else request or {'url': '/pl/film/'}
        self.history, self.page = [], {'title': 'CANAL+ VOD', 'items': [], 'description': ''}
        self.container = None
        self.running = self.closed = self.delivered = False
        self.buffer = ''
        self.decoder = codecs.getincrementaldecoder('utf-8')('replace')
        self.timer = eTimer()
        self.timer.callback.append(self.reload)
        self.onFirstExecBegin.append(lambda: self.timer.start(100, True))
        self.onClose.append(self.cleanup)

    def detach(self):
        if self.container is not None:
            for event, callback in [(self.container.dataAvail, self.data), (self.container.appClosed, self.finished)]:
                if callback in event:
                    event.remove(callback)

    def cancel_worker(self):
        self.detach()
        if self.container is not None and self.running:
            self.container.sendCtrlC()
        self.container, self.running, self.buffer = None, False, ''

    def reload(self, force=False):
        if self.closed or self.running:
            return
        request = self.request.get('refresh', self.request) if force else self.request
        if 'inline' in request:
            self.show_page(self.request['inline'])
            return
        self.detach()
        self.container = eConsoleAppContainer()
        self.container.dataAvail.append(self.data)
        self.container.appClosed.append(self.finished)
        self.buffer, self.delivered, self.running = '', False, True
        self.decoder = codecs.getincrementaldecoder('utf-8')('replace')
        self['status'].setText('Pobieranie katalogu CANAL+...  ·  EXIT: anuluj')
        python = '/usr/bin/python3'
        args = [python, python, '-u', str(Path(__file__).with_name('vod_worker.py'))]
        if 'search' in request:
            args += ['--search', request['search']]
        else:
            args += ['--request', json.dumps(request, ensure_ascii=False)]
        if self.container.execute(*args):
            self.finished(1)

    def data(self, chunk):
        if self.closed or not self.running:
            return
        value = self.decoder.decode(chunk) if isinstance(chunk, bytes) else chunk
        self.buffer += value
        if len(self.buffer) > 4 * 1024 * 1024:
            self.cancel_worker()
            self['status'].setText('Odpowiedź katalogu jest zbyt duża. EXIT: wróć.')
            return
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            try:
                event = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(event, dict):
                continue
            if event.get('stage') == 'vod_loaded' and isinstance(event.get('page'), dict):
                self.delivered = True
                self.show_page(event['page'])
            elif event.get('stage') == 'error':
                self.delivered = True
                reason = event.get('reason', 'vod_error')
                self['status'].setText(ERRORS.get(reason, 'Błąd katalogu: ' + str(reason)) + '\nŻÓŁTY: ponów · EXIT: wróć')

    def finished(self, code):
        self.running = False
        if not self.closed and not self.delivered:
            self['status'].setText('Nie udało się pobrać katalogu. ŻÓŁTY: ponów · EXIT: wróć')
        self.detach()
        self.container = None

    def show_page(self, page):
        self.page = page
        self['title'].setText(str(page.get('title', 'CANAL+ VOD'))[:250])
        items = [(('▶ ' if i.get('kind') == 'play' and not i.get('title', '').startswith('▶') else '')
                  + str(i.get('title', 'Pozycja')), i) for i in page.get('items', []) if isinstance(i, dict)]
        self['items'].setList(items)
        self.selection_changed()
        self['status'].setText('OK: otwórz / odtwórz  ·  Dostęp do VOD sprawdzamy przy odtwarzaniu.' if items else
                               'Brak pozycji na tej stronie. EXIT: wróć · ZIELONY: szukaj')

    def selection_changed(self):
        item = self['items'].getCurrent()
        description = item[1].get('description') if item else ''
        self['description'].setText(description or self.page.get('description') or
            'Katalog CANAL+. Film lub odcinek musi być dostępny w Twoim abonamencie.\n\nINFO: pełny opis')

    def select(self):
        if self.running or self.closed:
            return
        item = self['items'].getCurrent()
        if item is None:
            return
        value = item[1]
        if value.get('kind') == 'play':
            from .plugin import CanalE2Player
            self.session.open(CanalE2Player, value['id'], value['title'].replace('▶ Odtwórz · ', ''),
                              True, value.get('description') or self.page.get('description', ''))
        elif isinstance(value.get('request'), dict):
            index = self['items'].getSelectionIndex() if hasattr(self['items'], 'getSelectionIndex') else 0
            self.history.append((self.request, self.page, index))
            self.request = value['request']
            self.reload()

    def back(self):
        self.timer.stop()
        self.cancel_worker()
        if self.history:
            self.request, page, index = self.history.pop()
            self.show_page(page)
            if hasattr(self['items'], 'moveToIndex'):
                self['items'].moveToIndex(index)
        else:
            self.close()

    def search(self):
        if self.running:
            return
        from Screens.VirtualKeyBoard import VirtualKeyBoard
        self.session.openWithCallback(self.search_received, VirtualKeyBoard,
                                      title='Szukaj filmu lub serialu w CANAL+', text='')

    def search_received(self, query):
        if not self.closed and isinstance(query, str) and query.strip():
            self.history.append((self.request, self.page, 0))
            self.request = {'search': query.strip()[:160]}
            self.reload()

    def details(self):
        if self.running:
            return
        item = self['items'].getCurrent()
        title = item[1].get('title') if item else self.page.get('title')
        description = item[1].get('description') if item else ''
        self.session.open(CanalVodDescription, title or 'CANAL+ VOD', description or self.page.get('description', ''))

    def cleanup(self):
        self.closed = True
        self.timer.stop()
        self.cancel_worker()
        if self.selection_changed in self['items'].onSelectionChanged:
            self['items'].onSelectionChanged.remove(self.selection_changed)
