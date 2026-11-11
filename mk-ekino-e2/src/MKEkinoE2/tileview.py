# SPDX-License-Identifier: GPL-3.0-only
"""Four large native poster cards; bounded asynchronous artwork loading."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Screens.Screen import Screen
from enigma import eTimer,ePicLoad,eConsoleAppContainer

ROOT=Path(__file__).resolve().parent


def is_next_page(entry):
    return entry.get('pagination') is True or (entry.get('action')=='page' and entry.get('title')=='Następna strona')


def grid_skin():
    parts=['''<screen name="MKEkinoTiles" position="center,center" size="1200,650" title="MK Ekino — kafelki" backgroundColor="#0b101b">
      <widget name="heading" position="30,22" size="1140,45" font="Regular;29" foregroundColor="#55c9d1" zPosition="1" />
      <widget name="detail" position="30,552" size="1140,44" font="Regular;20" foregroundColor="#a9bed5" zPosition="1" />
      <widget name="hint" position="30,599" size="1140,48" font="Regular;20" foregroundColor="#ffffff" zPosition="1" />''']
    for i in range(4):
        x=24+i*290
        parts.extend([
            '<widget name="mark%d" position="%d,118" size="216,316" pixmap="%s" alphatest="blend" zPosition="5" />' % (i,x+27,ROOT/'poster_focus.png'),
            '<widget name="next%d" position="%d,126" size="200,300" pixmap="%s" alphatest="on" zPosition="2" />' % (i,x+35,ROOT/'next_page.png'),
            '<widget name="empty%d" position="%d,126" size="200,300" font="Regular;24" halign="center" valign="center" backgroundColor="#142033" foregroundColor="#6c8aa6" zPosition="1" />' % (i,x+35),
            '<widget name="cover%d" position="%d,126" size="200,300" alphatest="on" zPosition="2" />' % (i,x+35),
            '<widget name="title%d" position="%d,439" size="270,66" font="Regular;23" halign="center" foregroundColor="#ffffff" zPosition="1" />' % (i,x),
            '<widget name="rating%d" position="%d,511" size="270,28" font="Regular;20" halign="center" foregroundColor="#f3d375" zPosition="1" />' % (i,x)])
    return ''.join(parts)+'</screen>'


class PosterGrid(Screen):
    skin=grid_skin()

    def __init__(self,session,entries,index=0):
        Screen.__init__(self,session)
        self.entries=entries;self.index=max(0,min(index,len(entries)-1));self.page=-1
        self.closed=False;self.process=None;self.folder=None;self.generation=0
        self['heading']=Label('MK Ekino — filmy i seriale');self['detail']=Label('')
        self['hint']=Label('←/→: wybierz · ↑/↓ / CH−/CH+: strona · OK: otwórz · EXIT: wróć\nŻÓŁTY: lista · NIEBIESKI: aktualizacja · MENU: opcje')
        self.decoders=[];self.callbacks=[];self.decoding=[None]*4;self.loaded=[None]*4
        for i in range(4):
            self['mark%d'%i]=Pixmap();self['next%d'%i]=Pixmap();self['empty%d'%i]=Label('')
            self['cover%d'%i]=Pixmap();self['title%d'%i]=Label('');self['rating%d'%i]=Label('')
            decoder=ePicLoad();callback=lambda *args,slot=i:self.decoded(slot)
            decoder.PictureData.get().append(callback);self.decoders.append(decoder);self.callbacks.append(callback)
        self['actions']=ActionMap(['OkCancelActions','NavigationActions','DirectionActions','MenuActions','ColorActions'],{
            'ok':self.choose,'cancel':self.back,'menu':self.options,'yellow':self.list_view,'blue':self.updates,
            'left':lambda:self.move(-1),'right':lambda:self.move(1),
            'up':lambda:self.move(-4),'down':lambda:self.move(4),
            'pageUp':lambda:self.move(-4),'pageDown':lambda:self.move(4)},-3)
        self.timer=eTimer();self.timer.callback.append(self.fetch_covers)
        self.onLayoutFinish.append(self.layout_finished);self.onClose.append(self.cleanup)

    def layout_finished(self):self.render()

    def move(self,delta):
        self.index=max(0,min(self.index+delta,len(self.entries)-1));self.render()

    def render(self):
        page=self.index//4
        if page!=self.page:
            self.page=page;self.generation+=1;self.loaded=[None]*4
            for i in range(4):
                index=page*4+i;entry=self.entries[index] if index<len(self.entries) else {}
                self['cover%d'%i].hide()
                (self['next%d'%i].show if is_next_page(entry) else self['next%d'%i].hide)()
                self['empty%d'%i].setText('')
                self['title%d'%i].setText(('✓ ' if entry.get('watched') else '')+entry.get('title',''))
                self['rating%d'%i].setText(entry.get('rating_label','').split(' · ')[0])
            self.timer.start(200,True)
        for i in range(4):
            marker=self['mark%d'%i]
            if self.entries and self.index==page*4+i:marker.show()
            else:marker.hide()
        entry=self.entries[self.index] if self.entries else {}
        self['heading'].setText('MK Ekino — %d / %d' % (self.index+1,len(self.entries)))
        self['detail'].setText(entry.get('progress_label') or entry.get('synopsis') or entry.get('desc',''))

    def current_url(self,slot):
        index=self.page*4+slot
        return self.entries[index].get('icon','') if index<len(self.entries) and not is_next_page(self.entries[index]) else ''

    def cached(self,url):
        if not url:return None
        key=hashlib.sha256(url.encode()).hexdigest()
        for suffix in ('.jpg','.png'):
            path=Path('/tmp/mk-ekino-posters')/(key+suffix)
            if path.is_file():return path

    def stop_fetch(self):
        if self.process is not None:
            for event,callback in [(self.process.dataAvail,self.data),(self.process.appClosed,self.fetched)]:
                if callback in event:event.remove(callback)
            self.process.sendCtrlC();self.process=None

    def fetch_covers(self):
        if self.closed:return
        self.stop_fetch();self.decode_available()
        urls=list(dict.fromkeys(self.current_url(i) for i in range(4) if self.current_url(i) and not self.cached(self.current_url(i))))
        if not urls:return
        if self.folder is None:self.folder=Path(tempfile.mkdtemp(prefix='mk-ekino-grid-'))
        batch=self.folder/'posters.json';batch.write_text(json.dumps(urls));batch.chmod(0o600)
        self.process=eConsoleAppContainer();self.process.dataAvail.append(self.data);self.process.appClosed.append(self.fetched)
        python='/usr/bin/python3'
        if self.process.execute(python,python,str(ROOT/'poster.py'),'--batch',str(batch)):self.fetched(1)

    def data(self,*args):
        if not self.closed:self.decode_available()

    def fetched(self,*args):
        if self.process is not None:
            for event,callback in [(self.process.dataAvail,self.data),(self.process.appClosed,self.fetched)]:
                if callback in event:event.remove(callback)
            self.process=None
        if not self.closed:self.decode_available()

    def decode_available(self):
        for i in range(4):
            url=self.current_url(i);path=self.cached(url)
            if not path or self.decoding[i] or self.loaded[i]==(self.generation,url):continue
            widget=self['cover%d'%i]
            if not widget.instance:continue
            self.decoding[i]=(self.generation,url)
            width,height=widget.getSize();self.decoders[i].setPara((width,height,1,1,False,1,'#00142033'))
            if self.decoders[i].startDecode(str(path)):self.decoding[i]=None

    def decoded(self,slot):
        if self.closed:return
        token=self.decoding[slot];self.decoding[slot]=None
        if token==(self.generation,self.current_url(slot)):
            pointer=self.decoders[slot].getData()
            if pointer is not None and self['cover%d'%slot].instance:
                self['cover%d'%slot].instance.setPixmap(pointer);self['cover%d'%slot].show();self.loaded[slot]=token
        self.decode_available()

    def choose(self):self.close(('select',self.index))
    def back(self):self.close(('back',self.index))
    def list_view(self):self.close(('list',self.index))
    def options(self):self.close(('options',self.index))
    def updates(self):self.close(('updates',self.index))

    def cleanup(self):
        self.closed=True;self.timer.stop();self.stop_fetch()
        for decoder,callback in zip(self.decoders,self.callbacks):
            callbacks=decoder.PictureData.get()
            if callback in callbacks:callbacks.remove(callback)
        if self.folder:shutil.rmtree(self.folder,ignore_errors=True)
