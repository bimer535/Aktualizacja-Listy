# SPDX-License-Identifier: GPL-3.0-only
"""Native MK Kino cinema screens; artwork is fetched off the GUI thread."""
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
try:
    from .design import grid_skin,NAV
    from .cinema_data import panorama
except ImportError:
    from design import grid_skin,NAV
    from cinema_data import panorama
ROOT=Path(__file__).resolve().parent

class PosterGrid(Screen):
    def __init__(self,session,entries,index=0,context=None,mode=None):
        self.context=context or {}
        self.mode=mode or ('home' if self.context.get('action')=='main' else 'sources' if self.context.get('action')=='sources' else 'seasons' if self.context.get('action')=='seasons' else 'catalogue')
        self.skin=grid_skin(self.mode)
        Screen.__init__(self,session)
        self.slots=4 if self.mode in ('sources','seasons') else 5
        self.compact=self.mode in ('sources','seasons')
        self.entries=entries;self.index=max(0,min(index,len(entries)-1));self.page=-1
        self.closed=False;self.process=None;self.folder=None;self.generation=0
        self.zone='hero' if self.mode=='home' else 'cards';self.nav_index=0 if self.mode=='home' else 1
        self.hero_rows=panorama(entries);self.hero_pos=0
        self.backdrop_url='';self.backdrop_loading='';self.backdrop_loaded=''
        for name in ('wallpaper','backdrop','shade','logo','header','hero_focus'):self[name]=Pixmap()
        self['brand']=Label('MK KINO')
        for i,title in enumerate(NAV):self['nav%d'%i]=Label(title);self['navmark%d'%i]=Pixmap()
        for name in ('hero_meta','hero_title','hero_desc','hero_count','hero_action','heading','detail','hint'):self[name]=Label('')
        self['hero_action'].setText('▶ Oglądaj teraz')
        self['hint'].setText('← → wybierz · OK otwórz · ↑ menu · INFO pełny opis · ŻÓŁTY lista · EXIT wróć')
        self.decoders=[];self.callbacks=[];self.decoding=[None]*self.slots;self.loaded=[None]*self.slots
        for i in range(self.slots):
            self['cardbg%d'%i]=Pixmap();self['mark%d'%i]=Pixmap();self['empty%d'%i]=Label('')
            self['cover%d'%i]=Pixmap();self['title%d'%i]=Label('');self['rating%d'%i]=Label('')
            decoder=ePicLoad();callback=lambda *args,slot=i:self.decoded(slot)
            decoder.PictureData.get().append(callback);self.decoders.append(decoder);self.callbacks.append(callback)
        self.wide_decoder=ePicLoad();self.wide_decoder.PictureData.get().append(self.wide_decoded)
        self['actions']=ActionMap(['OkCancelActions','NavigationActions','DirectionActions','MenuActions','ColorActions','InfoActions'],{
            'ok':self.choose,'cancel':self.back,'menu':self.options,'yellow':self.list_view,'info':self.details,
            'left':lambda:self.direction(-1),'right':lambda:self.direction(1),
            'up':self.up,'down':self.down,'pageUp':lambda:self.move(-self.slots),'pageDown':lambda:self.move(self.slots)},-3)
        self.timer=eTimer();self.timer.callback.append(self.fetch_covers)
        self.rotation=eTimer();self.rotation.callback.append(self.rotate)
        self.onLayoutFinish.append(self.layout_finished);self.onClose.append(self.cleanup)

    def layout_finished(self):
        self['backdrop'].hide();self.render()
        if self.mode=='home':self.rotation.start(5000,False)

    def direction(self,delta):
        if self.zone=='nav':self.nav_index=(self.nav_index+delta)%len(NAV);self.marks()
        elif self.mode=='home':self.show_hero(delta)
        else:self.move(delta)

    def up(self):
        if self.zone!='nav':self.zone='nav';self.marks()
    def down(self):
        if self.zone=='nav':self.zone='hero' if self.mode=='home' else 'cards';self.marks()
        elif self.mode=='home':self.close(('expand',self.index))
        else:self.move(self.slots)
    def move(self,delta):
        self.index=max(0,min(self.index+delta,len(self.entries)-1));self.render()
    def marks(self):
        for i in range(len(NAV)):
            (self['navmark%d'%i].show if self.zone=='nav' and i==self.nav_index else self['navmark%d'%i].hide)()
        for i in range(self.slots):
            (self['mark%d'%i].show if self.zone=='cards' and self.index==self.page*self.slots+i else self['mark%d'%i].hide)()
        if self.mode=='home':(self['hero_focus'].show if self.zone=='hero' else self['hero_focus'].hide)()
    def rotate(self):
        if not self.closed and self.zone=='hero' and len(self.hero_rows)>1:self.show_hero(1)
    def show_hero(self,delta=0):
        if self.hero_rows:
            self.hero_pos=(self.hero_pos+delta)%len(self.hero_rows);entry=self.hero_rows[self.hero_pos]
            self.index=self.entries.index(entry)
        else:entry=self.context if self.compact else (self.entries[self.index] if self.entries else {})
        self['hero_title'].setText(entry.get('movie_title') or entry.get('title','MK Kino'))
        self['hero_meta'].setText(' · '.join(str(entry.get(k,'')) for k in ('year','language_version','rating_label') if entry.get(k)))
        text=entry.get('synopsis') or entry.get('desc','')
        self['hero_desc'].setText(text[:450])
        self['hero_count'].setText('%02d / %02d'%(self.hero_pos+1,len(self.hero_rows)) if self.hero_rows else '')
        wide=entry.get('backdrop','')
        if wide!=self.backdrop_url:
            self.backdrop_url=wide;self['backdrop'].hide();self.timer.start(200,True)
    def render(self):
        page=0 if self.mode=='home' else self.index//self.slots
        if page!=self.page:
            self.page=page;self.generation+=1;self.loaded=[None]*self.slots
            for i in range(self.slots):
                index=page*self.slots+i;entry=self.entries[index] if index<len(self.entries) else {}
                self['cover%d'%i].hide();self['empty%d'%i].setText('')
                (self['cardbg%d'%i].show if entry else self['cardbg%d'%i].hide)()
                self['title%d'%i].setText(('✓ ' if entry.get('watched') else '')+entry.get('title',''))
                self['rating%d'%i].setText(entry.get('rating_label','').split(' · ')[0] or entry.get('year',''))
            self.timer.start(200,True)
        self['heading'].setText('Ostatnio dodane filmy · 2026' if self.mode=='home' else 'Wybierz hosting' if self.mode=='sources' else 'Wybierz sezon' if self.mode=='seasons' else (self.context.get('title','Filmy i seriale')+' · %d / %d'%(self.index+1,len(self.entries))))
        entry=self.entries[self.index] if self.entries else {}
        self['detail'].setText('INFO: przeczytaj pełny opis' if self.mode=='home' or self.compact else entry.get('progress_label') or entry.get('year',''))
        if self.mode=='home' or self.compact:self.show_hero()
        self.marks()
    def current_url(self,slot):
        if self.compact:return self.context.get('icon','') if slot==0 else ''
        index=self.page*self.slots+slot
        return self.entries[index].get('icon','') if index<len(self.entries) else ''

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
        urls=list(dict.fromkeys(self.current_url(i) for i in range(self.slots) if self.current_url(i) and not self.cached(self.current_url(i))))
        if self.backdrop_url and not self.cached(self.backdrop_url):urls.append(self.backdrop_url)
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
        self.decode_wide()
        for i in range(self.slots):
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

    def decode_wide(self):
        url=self.backdrop_url;path=self.cached(url)
        if not path or self.backdrop_loading or self.backdrop_loaded==url:return
        widget=self['backdrop']
        if not widget.instance:return
        self.backdrop_loading=url
        width,height=widget.getSize();self.wide_decoder.setPara((width,height,1,1,False,1,'#000b1429'))
        if self.wide_decoder.startDecode(str(path)):self.backdrop_loading=''
    def wide_decoded(self,*args):
        if self.closed:return
        if self.backdrop_loading==self.backdrop_url:
            pointer=self.wide_decoder.getData()
            if pointer is not None and self['backdrop'].instance:
                self['backdrop'].instance.setPixmap(pointer);self['backdrop'].show();self.backdrop_loaded=self.backdrop_url
        self.backdrop_loading='';self.decode_wide()
    def choose(self):
        if self.zone=='nav':self.close(('route',self.nav_index))
        elif self.entries:self.close(('select',self.index))
    def back(self):self.close(('back',self.index))
    def list_view(self):self.close(('list',self.index))
    def options(self):self.close(('options',self.index))
    def details(self):self.close(('description',self.index))

    def cleanup(self):
        self.closed=True;self.timer.stop();self.rotation.stop();self.stop_fetch()
        wide=self.wide_decoder.PictureData.get()
        if self.wide_decoded in wide:wide.remove(self.wide_decoded)
        for decoder,callback in zip(self.decoders,self.callbacks):
            callbacks=decoder.PictureData.get()
            if callback in callbacks:callbacks.remove(callback)
        if self.folder:shutil.rmtree(self.folder,ignore_errors=True)
