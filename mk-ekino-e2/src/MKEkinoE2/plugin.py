# SPDX-License-Identifier: GPL-3.0-only
"""MK Ekino E2: independent catalogue and native Enigma2 playback UI."""
import json
import inspect
import hashlib
from pathlib import Path
import shutil
import tempfile
import time
import urllib.parse

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Components.ScrollLabel import ScrollLabel
from Plugins.Plugin import PluginDescriptor
from Screens.ChoiceBox import ChoiceBox
from Screens.InfoBar import MoviePlayer
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.VirtualKeyBoard import VirtualKeyBoard
from enigma import eConsoleAppContainer, eServiceReference, eTimer, ePicLoad

ROOT=Path(__file__).resolve().parent
try:
    from . import watchstate, playdiag
    from .tileview import PosterGrid
    from .design import main_skin,description_skin
except ImportError:
    import watchstate, playdiag
    from tileview import PosterGrid
    from design import main_skin,description_skin
VERSION='0.2.13'
HISTORY=Path('/etc/mk-ekino-e2/history.json')


def external_player_available():
    folder=Path('/usr/lib/enigma2/python/Plugins/SystemPlugins/ServiceApp')
    installed=(folder/'plugin.py').is_file() or (folder/'plugin.pyc').is_file()
    return installed and bool(shutil.which('exteplayer3'))


def read_history():
    try:
        values=json.loads(HISTORY.read_text())
        return [s for s in values if isinstance(s,str) and 0<len(s)<=200][:20] if isinstance(values,list) else []
    except (OSError,ValueError):return []


def save_history(term):
    values=[term]+[s for s in read_history() if s!=term]
    HISTORY.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    path=HISTORY.with_suffix('.tmp')
    fd=__import__('os').open(path,__import__('os').O_CREAT|__import__('os').O_TRUNC|__import__('os').O_WRONLY,0o600)
    with __import__('os').fdopen(fd,'w',encoding='utf-8') as out:json.dump(values[:20],out,ensure_ascii=False)
    path.replace(HISTORY)


class Notices(Screen):
    skin='''<screen name="MKEkinoNotices" position="center,center" size="1160,630" title="MK Kino — informacje i licencja">
      <widget name="text" position="25,20" size="1110,565" font="Regular;19" />
      <widget name="hint" position="25,590" size="1110,30" font="Regular;20" />
    </screen>'''
    def __init__(self,session):
        Screen.__init__(self,session)
        self['text']=ScrollLabel((ROOT/'NOTICE.txt').read_text()+'\n'+(ROOT/'LICENSE').read_text())
        self['hint']=Label('↑/↓ lub CH+/CH−: przewiń · EXIT: wróć')
        self['actions']=ActionMap(['OkCancelActions','NavigationActions'],{'cancel':self.close,'ok':self.close,
            'up':self['text'].pageUp,'down':self['text'].pageDown,
            'pageUp':self['text'].pageUp,'pageDown':self['text'].pageDown},-2)


class Contact(Screen):
    skin='''<screen name="MKEkinoContact" position="center,center" size="1100,560" title="MK Kino — autor i kontakt" backgroundColor="#0b101b">
      <widget name="heading" position="35,25" size="1030,45" font="Regular;34" foregroundColor="#55c9d1" zPosition="1" />
      <widget name="author" position="35,88" size="660,40" font="Regular;27" foregroundColor="#ffffff" zPosition="1" />
      <widget name="email" position="35,151" size="660,50" font="Regular;36" foregroundColor="#f3d375" zPosition="1" />
      <widget name="text" position="35,226" size="660,225" font="Regular;23" foregroundColor="#c7d4e8" zPosition="1" />
      <widget name="qr" position="780,112" size="264,264" zPosition="2" />
      <widget name="qr_hint" position="750,398" size="320,73" font="Regular;21" halign="center" foregroundColor="#a9bed5" zPosition="1" />
      <widget name="hint" position="35,507" size="1030,30" font="Regular;22" foregroundColor="#ffffff" zPosition="1" />
    </screen>'''

    def __init__(self,session):
        Screen.__init__(self,session)
        self['heading']=Label('MK Ekino E2 · '+VERSION)
        self['author']=Label('Projekt i rozwój wtyczki: MK')
        self['email']=Label('bimer55@wp.pl')
        self['text']=Label('Pomysły na nowe funkcje i zgłoszenia błędów.\n\nPrzy zgłoszeniu podaj:\n• model dekodera i wersję OpenATV,\n• wersję wtyczki,\n• krótki opis problemu.')
        self['qr']=Pixmap();self['qr_hint']=Label('Zeskanuj telefonem,\naby napisać wiadomość e-mail.')
        self['hint']=Label('OK / EXIT: wróć · INFO w przeglądarce: licencja')
        self['actions']=ActionMap(['OkCancelActions'],{'ok':self.close,'cancel':self.close},-2)
        self.decoder=ePicLoad();self.decoder.PictureData.get().append(self.decoded);self.closed=False
        self.onLayoutFinish.append(self.layout_finished);self.onClose.append(self.cleanup)

    def layout_finished(self):
        width,height=self['qr'].getSize()
        self.decoder.setPara((width,height,1,1,False,1,'#00ffffff'))
        self.decoder.startDecode(str(ROOT/'contact_qr.png'))

    def decoded(self,*args):
        if self.closed:return
        pointer=self.decoder.getData()
        if pointer is not None and self['qr'].instance:self['qr'].instance.setPixmap(pointer)

    def cleanup(self):
        self.closed=True
        callbacks=self.decoder.PictureData.get()
        if self.decoded in callbacks:callbacks.remove(self.decoded)



try:
    from .seekcontrol import StreamSeekMixin
except ImportError:
    from seekcontrol import StreamSeekMixin

class EkinoMoviePlayer(StreamSeekMixin,MoviePlayer):
    skinName='MoviePlayer'
    ENABLE_RESUME_SUPPORT=False

    def __init__(self,session,service,mk_entry=None,mk_library=None,mk_resume=0,**kwargs):
        self.mk_entry=mk_entry or {};self.mk_library=mk_library
        self.mk_resume=mk_resume;self.mk_attempts=0;self.mk_seek_sent=False;self.mk_ended=False;self.mk_position=0;self.mk_duration=0
        self.mk_audio_done=False;self.mk_audio_attempts=0
        self.mk_started_at=time.monotonic();self.mk_diag_phase='opening';self.mk_native_error={}
        self.mk_leaving=False
        # OpenATV has fromMovieSelection; OpenPLi 9.2 has no such parameter.
        # Inspect before constructing: retrying __init__ after a TypeError can
        # initialise the native player twice and duplicate event handlers.
        parameters=inspect.signature(MoviePlayer.__init__).parameters
        if ('fromMovieSelection' not in parameters and
                not any(p.kind==inspect.Parameter.VAR_KEYWORD for p in parameters.values())):
            kwargs.pop('fromMovieSelection',None)
        MoviePlayer.__init__(self,session,service,**kwargs)
        self.mk_leaving=False
        # Close on key release, so the same EXIT cannot also move back in Ekino.
        self['mkExitActions']=ActionMap(['OkCancelActions','InfobarShowHideActions'],{
            'cancel':self.exit_to_ekino,'close':self.exit_to_ekino,'hide':self.exit_to_ekino},-10)
        self['mkNextActions']=ActionMap(['ColorActions'],{'blue':self.mk_next},-11)
        # OpenATV binds OK make to unPauseService and break to toggleShow.
        # Consume make; toggle once on break, with priority over both maps.
        self['mkPauseActions']=ActionMap(['OkCancelActions','InfobarSeekActions','InfobarShowHideActions'],{
            'ok':self.mk_consume_ok,'unPauseService':self.mk_consume_ok,
            'OK':self.mk_toggle_pause,'toggleShow':self.mk_toggle_pause,
            'OKLong':self.mk_consume_ok,'LongOKPressed':self.mk_consume_ok},-12)
        self.mk_init_seek_controls(ROOT/'seek_keymap.xml', 'MKEkinoStreamSeekActions')
        self.mk_timer=eTimer();self.mk_timer.callback.append(self.mk_tick)
        self.mk_save_ticks=0
        self.onLayoutFinish.append(self.mk_start)
        # Save before MoviePlayer restores the previously playing TV service.
        self.onClose.insert(0,self.mk_cleanup)

    def mk_consume_ok(self):return 1

    def mk_toggle_pause(self):
        if self.mk_leaving:return 1
        if self.mk_scrub_finish():return 1
        if self.seekstate==self.SEEK_STATE_PAUSE:self.unPauseService()
        else:
            self.pauseService()
            self.show()
        return 1

    def mk_start(self):
        if 'key_blue' in self and self.mk_entry.get('episode'):self['key_blue'].setText('Następny odcinek')
        self.mk_diagnostic('opening')
        self.mk_timer.start(1000,False)

    def mk_diagnostic(self,phase):
        self.mk_diag_phase=phase
        data={'version':VERSION,'phase':phase,
              'playback_service':5002 if self.mk_entry.get('playback_service')==5002 else 4097,
              'elapsed_ms':max(0,round((time.monotonic()-self.mk_started_at)*1000)),
              'position_seconds':self.mk_position,'duration_seconds':self.mk_duration}
        try:
            from enigma import iServiceInformation
            service=self.session.nav.getCurrentService()
            data['service_active']=service is not None
            info=service.info() if service else None
            if info:
                message=info.getInfoString(iServiceInformation.sUser+12)
                summary=playdiag.error_summary(message)
                if summary.get('native_error_present'):self.mk_native_error=summary
                for name,field in [('width','sVideoWidth'),('height','sVideoHeight')]:
                    value=info.getInfo(getattr(iServiceInformation,field))
                    if type(value) is int and 0<value<=16384:data[name]=value
        except (ImportError,AttributeError,TypeError,RuntimeError):pass
        data.update(self.mk_native_error or {'native_error_present':False})
        playdiag.write(data)

    def mk_sample(self):
        try:
            service=self.session.nav.getCurrentService();seek=service.seek() if service else None
            if seek is None:return None
            position=seek.getPlayPosition();duration=seek.getLength()
            if not position[0] and isinstance(position[1],int):self.mk_position=max(0,position[1]//90000)
            if not duration[0] and isinstance(duration[1],int):self.mk_duration=max(0,duration[1]//90000)
            return seek
        except (AttributeError,TypeError,RuntimeError):return None

    def mk_save(self,completed=False):
        self.mk_sample()
        if self.mk_library:
            try:self.mk_library.record(self.mk_entry,self.mk_position,self.mk_duration,completed)
            except (OSError,ValueError,TypeError):pass

    def mk_tick(self):
        seek=self.mk_sample();self.mk_save_ticks+=1
        if not self.mk_audio_done and self.mk_audio_attempts<20:
            self.mk_audio_attempts+=1
            try:
                service=self.session.nav.getCurrentService();tracks=service.audioTracks() if service else None
                if tracks:
                    for i in range(tracks.getNumberOfTracks()):
                        language=tracks.getTrackInfo(i).getLanguage().lower().replace(',',' ').replace('/',' ').split()
                        if any(code in ('pl','pol','polski','polish') for code in language):
                            tracks.selectTrack(i);self.mk_audio_done=True;break
            except (AttributeError,RuntimeError,TypeError):pass
        if self.mk_resume and self.mk_attempts<20:
            self.mk_attempts+=1
            try:
                if self.mk_seek_sent and abs(self.mk_position-self.mk_resume)<10:
                    self.mk_resume=0
                elif seek is not None and seek.isCurrentlySeekable() and (not self.mk_seek_sent or self.mk_attempts%3==0):
                    if seek.seekTo(int(self.mk_resume)*90000)==0:self.mk_seek_sent=True
            except (AttributeError,RuntimeError,TypeError):pass
            if self.mk_resume and self.mk_attempts==20:
                self.mk_resume=0
                self.session.open(MessageBox,'To źródło nie pozwoliło wznowić od zapisanej pozycji. Film jest odtwarzany od początku.',type=MessageBox.TYPE_INFO,timeout=7)
        if self.mk_save_ticks%15==0 and not self.mk_resume:self.mk_save(self.mk_ended)
        if self.mk_save_ticks<=10 or self.mk_save_ticks%5==0:self.mk_diagnostic('playing' if self.mk_position>0 else 'waiting_for_playback')

    def mk_cleanup(self):
        self.mk_timer.stop()
        if self.mk_tick in self.mk_timer.callback:self.mk_timer.callback.remove(self.mk_tick)
        self.mk_save(self.mk_ended)
        self.mk_diagnostic(self.mk_diag_phase)

    def leavePlayer(self):
        self.mk_save()
        MoviePlayer.leavePlayer(self)

    def doEofInternal(self,playing):
        if not playing or self.mk_leaving or not getattr(self,'execing',True):return
        self.mk_leaving=True
        self.mk_sample()
        self.mk_ended=self.mk_position>=15 and (not self.mk_duration or self.mk_position>=self.mk_duration-30)
        self.mk_save(self.mk_ended)
        early=not self.mk_ended and self.mk_position<15
        self.mk_diagnostic('stopped_before_playback' if early else 'eof')
        result={'completed':self.mk_ended}
        if early:result['playback_error']='playback_stopped_early'
        self.close(result)

    def mk_next(self):
        if not self.mk_entry.get('episode') or self.mk_leaving:return 0
        self.mk_leaving=True
        self.mk_save();self.close({'next':True})
        return 1

    def leavePlayerOnExit(self):
        return 1  # Consume the make event; the release above stops playback.

    def exit_to_ekino(self):
        if not self.mk_leaving:
            self.mk_leaving=True
            self.leavePlayer()
        return 1


class Updates(Screen):
    skin='''<screen name="MKEkinoUpdates" position="center,center" size="1050,470" title="MK Kino — aktualizacja">
      <widget name="text" position="30,25" size="990,350" font="Regular;25" />
      <widget name="hint" position="30,400" size="990,40" font="Regular;22" foregroundColor="#66aaff" />
    </screen>'''

    def __init__(self,session):
        Screen.__init__(self,session)
        self['text']=Label('Zainstalowana wersja: '+VERSION+'\nSprawdzanie aktualizacji na GitHubie…')
        self['hint']=Label('EXIT: wróć')
        self['actions']=ActionMap(['OkCancelActions','ColorActions'],{
            'cancel':self.back,'ok':self.confirm,'blue':self.confirm,'green':self.confirm},-2)
        self.container=None;self.busy=False;self.installing=False;self.closed=False
        self.release=None;self.buffer='';self.restart_needed=False
        self.timer=eTimer();self.timer.callback.append(self.check)
        self.onLayoutFinish.append(self.layout_finished);self.onClose.append(self.cleanup)

    def layout_finished(self):self.timer.start(150,True)

    def check(self):self.run(False)

    def run(self,install):
        if self.busy or self.closed:return
        self.busy=True;self.installing=install;self.buffer=''
        self.container=eConsoleAppContainer()
        self.container.dataAvail.append(self.data);self.container.appClosed.append(self.finished)
        python='/usr/bin/python3'
        args=[python,python,'-u',str(ROOT/'updater.py'),'--current',VERSION]
        if install:
            args+=['--install','--expected-version',self.release['version'],'--expected-sha',self.release['sha256']]
            self['text'].setText('Pobieranie, sprawdzanie i instalacja wersji '+self.release['version']+'…')
            self['hint'].setText('Poczekaj na zakończenie instalacji.')
        if self.container.execute(*args):self.finished(1)

    def data(self,data):
        if not self.closed:self.buffer=(self.buffer+(data.decode('utf-8','replace') if isinstance(data,bytes) else data))[-32768:]

    def detach(self):
        if self.container is not None:
            for event,callback in [(self.container.dataAvail,self.data),(self.container.appClosed,self.finished)]:
                if callback in event:event.remove(callback)
            self.container=None

    def finished(self,code):
        self.busy=False;self.detach()
        if self.closed:return
        result={}
        for line in self.buffer.splitlines():
            try:
                candidate=json.loads(line)
                if isinstance(candidate,dict):result=candidate
            except ValueError:pass
        status=result.get('status')
        self['hint'].setText('EXIT: wróć')
        if code==0 and status=='available' and isinstance(result.get('version'),str) and isinstance(result.get('sha256'),str):
            self.release=result
            self['text'].setText('Zainstalowana: '+VERSION+'\nDostępna: '+result['version']+'\n\n'+result.get('notes',''))
            self['hint'].setText('OK / niebieski: zainstaluj · EXIT: wróć')
        elif code==0 and status=='current':
            self['text'].setText('Wersja '+VERSION+' jest aktualna.')
        elif code==0 and status=='installed':
            self.restart_needed=True;self.release=None
            self['text'].setText('Zainstalowano wersję '+result['version']+'.\nUruchom ponownie interfejs Enigma2, aby jej użyć.')
            self['hint'].setText('OK: restart interfejsu · EXIT: restart później')
            self.confirm()
        else:
            self.release=None
            messages={'checksum_mismatch':'Pobrany plik jest niekompletny lub ma niezgodną sumę kontrolną.',
                'install_failed':'Instalacja nie powiodła się. Sprawdź wolne miejsce i dostępność zależności.',
                'installed_version_not_confirmed':'Nie potwierdzono nowej wersji w menedżerze pakietów.',
                'release_changed':'Wydanie zmieniło się podczas sprawdzania. Otwórz aktualizacje ponownie.'}
            self['text'].setText(messages.get(result.get('reason'),'Nie udało się sprawdzić lub pobrać aktualizacji. Spróbuj ponownie później.'))

    def confirm(self):
        if self.busy:return
        if self.restart_needed:
            self.session.openWithCallback(self.restart,MessageBox,'Uruchomić ponownie interfejs Enigma2?',type=MessageBox.TYPE_YESNO,default=False)
        elif self.release:
            self.session.openWithCallback(self.accepted,MessageBox,'Zainstalować MK Ekino E2 '+self.release['version']+'?',type=MessageBox.TYPE_YESNO,default=False)

    def accepted(self,answer):
        if answer and self.release and not self.closed:self.run(True)

    def restart(self,answer):
        if answer and not self.closed:
            from Screens.Standby import TryQuitMainloop
            self.session.open(TryQuitMainloop,3)

    def back(self):
        if self.busy and self.installing:return
        self.close()

    def cleanup(self):
        self.closed=True;self.timer.stop()
        if self.busy and not self.installing and self.container is not None:self.container.sendCtrlC()
        self.detach()


class FullDescription(Screen):
    skin=description_skin()
    def __init__(self,session,title,text):
        Screen.__init__(self,session)
        self['wallpaper']=Pixmap();self['title']=Label(title);self['body']=ScrollLabel(text)
        self['hint']=Label('↑ ↓ / CH+ CH−: przewijaj · OK / EXIT: wróć')
        self['actions']=ActionMap(['OkCancelActions','DirectionActions','NavigationActions'],{'ok':self.close,'cancel':self.close,'up':self['body'].pageUp,'down':self['body'].pageDown,'pageUp':self['body'].pageUp,'pageDown':self['body'].pageDown},-4)


class MKEkino(Screen):
    skin=main_skin()
    def __init__(self,session):
        Screen.__init__(self,session)
        self['wallpaper']=Pixmap()
        self['heading']=Label('MK Kino')
        self.grid_mode_override=None
        self['version']=Label('WERSJA '+VERSION)
        self['selected_title']=Label('Filmy i seriale')
        self['rating']=Label('')
        self['metadata']=Label('')
        self['counter']=Label('')
        self['poster_hint']=Label('')
        self['poster']=Pixmap()
        self['path']=Label('Filmy i seriale')
        self['list']=MenuList([])
        self['description']=ScrollLabel('')
        self['status']=Label('OK: wybierz · ↑/↓: nawigacja')
        self['options_hint']=Label('INFO: pełny opis · MENU: opcje, ulubione i kontakt')
        self['red']=Label('Wyjdź / Wróć');self['green']=Label('Wyszukaj')
        self['yellow']=Label('Lista / kafelki');self['blue']=Label('Aktualizacja')
        self['actions']=ActionMap(['OkCancelActions','ColorActions','NavigationActions','InfoActions','MenuActions'],{
            'ok':self.select,'cancel':self.back,'red':self.back,'green':self.search,
            'yellow':self.toggle_view,'blue':self.updates,
            'info':self.details,'menu':self.options,
            'up':lambda:self.move('up'),'down':lambda:self.move('down'),
            'pageUp':lambda:self.move('pageUp'),'pageDown':lambda:self.move('pageDown')},-2)
        self['list'].onSelectionChanged.append(self.selection_changed)
        self.current={'action':'main','title':'Główna'};self.entries=[];self.stack=[]
        self.library=watchstate.Library();self.preferences=self.library.settings()
        self.after_job=None;self.grid_pending=False;self.playback_entry={};self.next_entry={}
        self.container=None;self.running=False;self.stopping=False;self.closed=False
        self.job_dir=None;self.pending=None;self.buffer='';self.push=False;self.playing=False
        self.cover_url='';self.cover_fetch_url='';self.cover_process=None;self.cover_decoding_url='';self.cover_pending=None
        self.cover_timer=eTimer();self.cover_timer.callback.append(self.request_cover)
        self.cover_decoder=ePicLoad();self.cover_decoder.PictureData.get().append(self.cover_decoded)
        self.timer=eTimer();self.timer.callback.append(lambda:self.load(self.current,push=False))
        self.onLayoutFinish.append(self.layout_finished)
        self.onClose.append(self.cleanup)

    def layout_finished(self):
        # OpenATV 7.4 treats plain functions in onLayoutFinish as exec() text.
        # A bound screen method is called normally by createGUIScreen.
        self.timer.start(150,True)

    def move(self,method):
        getattr(self['list'],method)()
        self.selection_changed()

    def selection_changed(self):
        value=self['list'].getCurrent()
        entry=value[1] if value else {}
        preview=dict(self.current) if entry.get('action')=='resolve' else {}
        preview.update(entry)
        self['description'].setText(preview.get('synopsis') or preview.get('desc') or 'Wybierz pozycję przyciskiem OK.\nCH+/CH−: następna lub poprzednia strona listy.')
        self['selected_title'].setText(entry.get('movie_title') or entry.get('series_title') or entry.get('title','MK Ekino E2'))
        self['rating'].setText(preview.get('rating_label','').replace(' · głosów:', '\ngłosów:'))
        self['metadata'].setText(preview.get('progress_label') or ' · '.join(str(preview.get(key,'')) for key in ('year','language_version') if preview.get(key)))
        self['counter'].setText(('%d / %d' % (self['list'].getSelectedIndex()+1,len(self.entries))) if self.entries else '')
        url=preview.get('icon','')
        if url!=self.cover_url:
            self.cover_url=url;self.cover_timer.stop();self.cover_pending=None
            self['poster'].hide();self['poster_hint'].setText('')
            if url:self.cover_timer.start(250,True)

    def cover_path(self):
        key=hashlib.sha256(self.cover_url.encode()).hexdigest()
        for suffix in ('.jpg','.png'):
            path=Path('/tmp/mk-ekino-posters')/(key+suffix)
            if path.is_file():return path
        return None

    def stop_cover_fetch(self):
        process=self.cover_process
        if process is not None:
            if self.cover_fetched in process.appClosed:process.appClosed.remove(self.cover_fetched)
            process.sendCtrlC();self.cover_process=None

    def request_cover(self):
        if self.closed or not self.cover_url:return
        path=self.cover_path()
        if path is not None:self.decode_cover(path);return
        self.stop_cover_fetch()
        self.cover_fetch_url=self.cover_url
        self.cover_process=eConsoleAppContainer();self.cover_process.appClosed.append(self.cover_fetched)
        python='/usr/bin/python3'
        if self.cover_process.execute(python,python,str(ROOT/'poster.py'),self.cover_url):self.cover_fetched(1)

    def cover_fetched(self,code):
        process=self.cover_process
        if process is not None and self.cover_fetched in process.appClosed:process.appClosed.remove(self.cover_fetched)
        self.cover_process=None
        if not code and not self.closed and self.cover_fetch_url==self.cover_url:
            path=self.cover_path()
            if path is not None:self.decode_cover(path)

    def decode_cover(self,path):
        if self.closed:return
        if self.cover_decoding_url:
            self.cover_pending=(self.cover_url,path);return
        if not self['poster'].instance:return
        self.cover_decoding_url=self.cover_url
        width,height=self['poster'].getSize()
        self.cover_decoder.setPara((width,height,1,1,False,1,'#001d3047'))
        if self.cover_decoder.startDecode(str(path)):
            self.cover_decoding_url=''

    def cover_decoded(self,*args):
        if self.closed:return
        if self.cover_decoding_url==self.cover_url:
            pointer=self.cover_decoder.getData()
            if pointer is not None and self['poster'].instance:
                self['poster'].instance.setPixmap(pointer);self['poster'].show()
                self['poster_hint'].setText('')
        self.cover_decoding_url=''
        pending=self.cover_pending;self.cover_pending=None
        if pending and pending[0]==self.cover_url:self.decode_cover(pending[1])

    def show_items(self,items):
        progress=self.library.read().get('progress',{})
        if isinstance(progress,dict):
            items=[dict(entry,watched=bool(progress.get(entry.get('url'),{}).get('completed')))
                   if isinstance(progress.get(entry.get('url'),{}),dict) else entry for entry in items]
        self.entries=items
        self['list'].setList([(self.display_title(x),x) for x in items])
        self['list'].moveToIndex(0)
        self['path'].setText(' > '.join([s[0].get('title','') for s in self.stack]+[self.current.get('title','Ekino')]))
        self['status'].setText('OK: wybierz · MENU: opcje / ulubione · %d pozycji' % len(items) if items else 'Brak pozycji. EXIT: wróć.')
        self.selection_changed()

    @staticmethod
    def display_title(entry):
        prefix='✓ ' if entry.get('watched') else ''
        if entry.get('rating_label') and isinstance(entry.get('rating'),(int,float)):
            if entry.get('rating_votes')==0:return prefix+'[brak ocen] '+entry['title']
            score=('%g' % entry['rating']).replace('.',',')
            return prefix+'['+score+'/10] '+entry['title']
        return prefix+entry['title']

    def select(self):
        value=self['list'].getCurrent()
        if not value or self.running:return
        entry=value[1]
        if entry['action']=='search':self.search()
        elif entry['action'] in ('favourites','continue'):self.local_list(entry)
        elif entry['action']=='history':
            self.stack.append((self.current,self.entries,self['list'].getSelectedIndex()))
            self.current=entry
            self.show_items([{'title':term,'action':'search_results','query':term} for term in read_history()])
        else:self.load(entry)

    def search(self):
        if self.running:return
        self.session.openWithCallback(self.search_done,VirtualKeyBoard,title='Tytuł filmu lub serialu',text='')

    def search_done(self,term):
        if not isinstance(term,str) or not term.strip():self.maybe_grid();return
        term=term.strip()[:200]
        try:save_history(term)
        except OSError:pass
        self.load({'action':'search_results','title':'Szukaj: '+term,'query':term})

    def refresh(self):
        if self.running:return
        if self.current.get('action') in ('favourites','continue'):self.local_list(self.current,False)
        elif self.current.get('action')=='history':
            self.show_items([{'title':term,'action':'search_results','query':term} for term in read_history()])
        else:self.load(self.current,push=False)

    def updates(self):
        if not self.running:self.session.open(Updates)

    def notices(self):self.session.open(Notices)

    def local_list(self,entry,push=True):
        if push:self.stack.append((self.current,self.entries,self['list'].getSelectedIndex()))
        self.current=entry
        values=self.library.favourites() if entry['action']=='favourites' else self.library.continuing()
        self.show_items(values);self.maybe_grid()

    def selected_entry(self):
        value=self['list'].getCurrent();entry=dict(value[1]) if value else {}
        if entry.get('action')=='resolve':
            entry=dict(entry,title=entry.get('movie_title','Film'),action='sources')
        return entry

    def toggle_view(self):
        if self.running or self.closed:return
        try:
            value='tiles' if self.preferences['view']=='list' else 'list'
            self.library.setting('view',value);self.preferences=self.library.settings()
            self['status'].setText('Widok kafelków włączony. Otwórz listę filmów lub seriali.' if value=='tiles' else 'Widok listy włączony.')
            self.maybe_grid()
        except OSError:self.error('local_state_write_failed')

    def options(self,return_to_grid=False):
        if self.running:return
        choices=[];entry=self.selected_entry()
        if watchstate.entry_copy(entry):
            present=any(value['url']==entry['url'] for value in self.library.favourites())
            choices.append(('Usuń z ulubionych' if present else 'Dodaj do ulubionych','favourite'))
        choices.extend([('Automat: '+('player / polski / najlepsza jakość' if self.preferences['auto_play'] else 'wyłączony — wybór ręczny')+' — zmień','auto'),
                        ('Widok: '+('kafelki' if self.preferences['view']=='tiles' else 'lista')+' — zmień','view')])
        choices.append(('Odtwarzacz: '+('exteplayer3 (5002)' if self.preferences['playback_service']==5002 else 'standardowy (4097)')+' — zmień','player'))
        if entry.get('episode') and entry.get('series_url'):choices.append(('Następny odcinek','next'))
        choices.append(('Odśwież listę','refresh'))
        choices.append(('Autor i kontakt','contact'))
        choices.append(('Informacje i licencja','info'))
        self.session.openWithCallback(lambda choice:self.option_selected(choice,return_to_grid),ChoiceBox,title='MK Kino — opcje',list=choices)

    def option_selected(self,choice,return_to_grid=False):
        if self.closed:return
        if not choice:
            if return_to_grid:self.maybe_grid()
            return
        action=choice[1]
        try:
            if action=='favourite':
                added=self.library.toggle(self.selected_entry())
                if self.current.get('action')=='favourites':self.show_items(self.library.favourites())
                self['status'].setText('Dodano do ulubionych.' if added else 'Usunięto z ulubionych.')
            elif action in ('auto','view'):
                key='auto_play' if action=='auto' else 'view'
                value=not self.preferences[key] if action=='auto' else ('tiles' if self.preferences[key]=='list' else 'list')
                self.library.setting(key,value);self.preferences=self.library.settings()
                self['status'].setText('Zapisano ustawienie. MENU: opcje')
            elif action=='player':
                self.session.openWithCallback(lambda value:self.player_selected(value,return_to_grid),ChoiceBox,
                    title='Odtwarzacz tylko dla MK Ekino',
                    list=[('Standardowy Enigma2 (4097)',4097),('exteplayer3 / ServiceApp (5002)',5002)])
                return
            elif action=='next':
                self.next_entry=self.selected_entry();self.next_confirmed(True);return
            elif action=='refresh':self.refresh();return
            elif action in ('contact','info'):
                screen=Contact if action=='contact' else Notices
                if return_to_grid:self.session.openWithCallback(self.maybe_grid,screen)
                else:self.session.open(screen)
                return
            if action=='view' or return_to_grid:self.maybe_grid()
        except OSError:self.error('local_state_write_failed')

    def player_selected(self,choice,return_to_grid=False):
        if self.closed:return
        if choice and choice[1] in (4097,5002):
            service=choice[1]
            if service==5002 and not external_player_available():
                self.error('serviceapp_required')
                return
            try:
                self.library.setting('playback_service',service)
                self.preferences=self.library.settings()
                self['status'].setText('Odtwarzacz: '+('exteplayer3 (5002)' if service==5002 else 'standardowy (4097)'))
            except OSError:self.error('local_state_write_failed');return
        if return_to_grid:self.maybe_grid()

    def maybe_grid(self,*args):
        kind=self.current.get('action')
        allowed=kind=='main' or any(entry.get('action') in ('sources','seasons','resolve','episodes') for entry in self.entries)
        if not self.closed and not self.running and allowed and (kind=='main' or self.preferences['view']=='tiles'):
            context=dict(self.current)
            if kind=='sources' and self.entries:context.update(self.entries[0],title=self.current.get('title','Film'),action=kind)
            self.session.openWithCallback(self.tile_selected,PosterGrid,self.entries,self['list'].getSelectedIndex(),context,self.grid_mode_override)

    def route(self,index):
        self.grid_mode_override=None
        if index==3:self.search();return
        if index==6:self.options(return_to_grid=True);return
        self.stack=[]
        entry={0:{'action':'main','title':'Główna'},1:{'action':'categories','title':'Filmy'},2:{'action':'series','title':'Seriale'},4:{'action':'favourites','title':'Ulubione'},5:{'action':'continue','title':'Oglądaj dalej'}}.get(index)
        if not entry:return
        if entry['action'] in ('favourites','continue'):self.local_list(entry,False)
        else:self.load(entry,push=False)

    def details(self):
        current=self.selected_entry()
        text=current.get('synopsis') or self.current.get('synopsis') or current.get('desc') or self.current.get('desc')
        if text:self.session.openWithCallback(self.maybe_grid,FullDescription,current.get('movie_title') or current.get('title','Opis filmu'),text)
        else:self.notices()

    def tile_selected(self,result=None):
        if self.closed or not result:return
        action,index=result
        if action=='route':self.route(index);return
        self['list'].moveToIndex(index);self.selection_changed()
        if action=='select':self.grid_mode_override=None;self.select()
        elif action=='expand':self.grid_mode_override='catalogue';self.maybe_grid()
        elif action=='back':
            if self.current.get('action')=='main' and self.grid_mode_override:
                self.grid_mode_override=None;self.maybe_grid()
            else:self.grid_mode_override=None;self.back()
        elif action=='description':self.details()
        elif action=='options':self.options(return_to_grid=True)
        elif action=='list':
            try:self.library.setting('view','list')
            except OSError:pass
            self.preferences['view']='list'

    def load(self,entry,push=True):
        if self.running or self.closed:return
        entry=dict(entry)
        if entry.get('action')=='resolve':
            entry.setdefault('auto_quality',self.preferences['auto_play'])
            entry['playback_service']=self.preferences['playback_service']
            if entry['playback_service']==5002 and not external_player_available():
                self.error('serviceapp_required');return
        self.release_job()
        self.job_dir=Path(tempfile.mkdtemp(prefix='mk-ekino-ui-'))
        self.pending=dict(entry);self.push=push
        (self.job_dir/'request.json').write_text(json.dumps({'item':entry},ensure_ascii=False))
        (self.job_dir/'request.json').chmod(0o600)
        self.container=eConsoleAppContainer()
        self.container.dataAvail.append(self.data)
        self.container.appClosed.append(self.finished)
        self.buffer='';self.stopping=False;self.running=True
        python='/usr/bin/python3'
        result=self.container.execute(python,python,'-u',str(ROOT/'worker.py'),
            '--request',str(self.job_dir/'request.json'),'--result',str(self.job_dir/'result.json'),
            '--control',str(self.job_dir/'control.json'))
        self['status'].setText('Pobieranie źródła...' if entry['action']=='resolve' else 'Pobieranie listy...')
        if result:self.running=False;self.error('worker_start_failed')

    def data(self,data):
        if self.closed or self.stopping:return
        self.buffer=(self.buffer+(data.decode('utf-8','replace') if isinstance(data,bytes) else data))[-65536:]
        while '\n' in self.buffer:
            line,self.buffer=self.buffer.split('\n',1)
            try:event=json.loads(line)
            except (ValueError,TypeError):continue
            stage=event.get('stage') if isinstance(event,dict) else None
            if stage=='catalogue_ready':
                try:items=json.loads((self.job_dir/'result.json').read_text())['items']
                except (OSError,ValueError,KeyError):self.error('invalid_worker_result');continue
                if self.pending.get('action')=='next_episode':
                    if items:self.after_job=items[0]
                    else:self.error('next_episode_unavailable')
                    continue
                if self.push:self.stack.append((self.current,self.entries,self['list'].getSelectedIndex()))
                self.current=self.pending;self.show_items(items)
                if self.current.get('action')=='sources' and items and self.preferences['auto_play']:
                    self.after_job=dict(items[0],auto_quality=True)
                else:self.grid_pending=True
            elif stage=='choose_variant':
                try:labels=json.loads((self.job_dir/'result.json').read_text())['variants']
                except (OSError,ValueError,KeyError):self.error('invalid_worker_result');self.stop_job();continue
                self.session.openWithCallback(self.variant_selected,ChoiceBox,title='Wybierz język i jakość',
                                              list=[(value,index) for index,value in enumerate(labels)])
            elif stage=='source_access_work':self['status'].setText('Weryfikacja źródła… może potrwać kilka minut. EXIT: anuluj.')
            elif stage=='variant_selected':self['status'].setText('Automatycznie: %s · %sp · uruchamianie…' % (event.get('language') or 'Auto',event.get('height') or 'Auto'))
            elif stage=='play_ready':self.play(event.get('url',''))
            elif stage=='error':self.error(event.get('reason','error'))

    def variant_selected(self,choice):
        if self.closed or self.stopping or not self.running:return
        if choice is None:self.stop_job();return
        path=self.job_dir/'selection.tmp'
        path.write_text(json.dumps({'index':choice[1]}));path.chmod(0o600)
        path.replace(self.job_dir/'control.json')
        self['status'].setText('Uruchamianie filmu...')

    def play(self,url):
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or not parsed.port:
            self.error('invalid_local_playback_address');self.stop_job();return
        self.playback_entry=dict(self.pending,action='sources',title=self.pending.get('movie_title','Film'))
        saved=self.library.progress(self.playback_entry.get('url',''))
        position=saved.get('position',0)
        if isinstance(position,(int,float)) and position>=15 and not saved.get('completed'):
            self.session.openWithCallback(lambda answer:self.start_movie(url,int(position) if answer else 0),MessageBox,
                                         'Wznowić od '+watchstate.stamp(position)+'?',type=MessageBox.TYPE_YESNO,default=True)
        else:self.start_movie(url,0)

    def start_movie(self,url,position):
        if self.closed or self.stopping or not self.running:return
        service=5002 if self.pending.get('playback_service',self.preferences['playback_service'])==5002 else 4097
        ref=eServiceReference(service,0,url)
        ref.setName(self.pending.get('movie_title','Ekino'))
        self.playback_entry['playback_service']=service
        self.playing=True
        self.session.openWithCallback(self.movie_closed,EkinoMoviePlayer,ref,fromMovieSelection=False,
                                      mk_entry=self.playback_entry,mk_library=self.library,mk_resume=position)

    def movie_closed(self,result=None):
        self.playing=False;self.stop_job()
        if isinstance(result,dict) and result.get('playback_error'):
            self.error('playback_stopped_early');return
        if isinstance(result,dict) and (result.get('completed') or result.get('next')) and self.playback_entry.get('series_url'):
            self.next_entry=dict(self.playback_entry)
            self.session.openWithCallback(self.next_confirmed,MessageBox,'Uruchomić następny odcinek?',type=MessageBox.TYPE_YESNO,default=True)

    def next_confirmed(self,answer):
        if not answer or self.closed:return
        entry=dict(self.next_entry,action='next_episode')
        if self.running:self.after_job=entry
        else:self.load(entry,push=False)

    def error(self,reason):
        messages={'upzone_transfer_limit':'Upzone: wyczerpany bezpłatny transfer lub wymagane konto premium. Wybierz inne źródło albo spróbuj później.',
                  'upzone_payload_not_found':'Upzone nie udostępniło adresu filmu. Odtwarzacz mógł się zmienić lub plik jest niedostępny.',
                  'upzone_address_not_supported':'Nie rozpoznano adresu odtwarzacza Upzone.',
                  'source_access_denied':'Serwer blokuje dostęp do tego źródła (HTTP 403 / weryfikacja). Wybierz player lub inne źródło.',
                  'source_not_supported':'Ten rodzaj źródła nie jest jeszcze obsługiwany. Wybierz player lub inne źródło.',
                  'watch_or_embed_http_error':'Źródło odmówiło dostępu. Odśwież listę źródeł lub spróbuj później.',
                  'source_returned_no_variants':'Źródło nie zwróciło dostępnych wariantów filmu.',
                  'catalogue_http_error':'Nie udało się pobrać katalogu. Sprawdź połączenie.',
                  'variant_selection_cancelled':'Wybór anulowany.'}
        messages.update(playback_stopped_early='Odtwarzacz zakończył pracę przed rozpoczęciem filmu. Zapisano diagnostykę: /tmp/mk_ekino_player.json oraz /tmp/mk_ekino_report.json.',
                        serviceapp_required='Do exteplayer3 potrzebny jest ServiceApp. W Telnecie: opkg update && opkg install enigma2-plugin-systemplugins-serviceapp. Następnie uruchom ponownie GUI i wybierz odtwarzacz w MENU.',
                        local_state_write_failed='Nie udało się zapisać danych wtyczki. Sprawdź wolne miejsce.',
                        next_episode_unavailable='Nie znaleziono listy kolejnych odcinków tego serialu.')
        text=messages.get(reason,'Nie udało się otworzyć pozycji: '+str(reason))
        self['status'].setText(text)
        self.session.open(MessageBox,text,type=MessageBox.TYPE_ERROR,timeout=12)

    def stop_job(self):
        if self.running and not self.stopping:
            self.stopping=True;self.container.sendCtrlC()
        elif not self.running:self.release_job()

    def finished(self,code):
        self.running=False;self.stopping=False
        if not self.closed and not self.playing:self['status'].setText('OK: wybierz · EXIT: wróć')
        self.release_job()
        after=self.after_job;self.after_job=None
        if not self.closed and after and not code:self.load(after,push=False)
        elif not self.closed and after and after.get('action')=='next_episode':self.load(after,push=False)
        elif self.grid_pending:
            self.grid_pending=False;self.maybe_grid()

    def release_job(self):
        if self.running:return
        if self.container is not None:
            for event,callback in [(self.container.dataAvail,self.data),(self.container.appClosed,self.finished)]:
                if callback in event:event.remove(callback)
            self.container=None
        if self.job_dir is not None:
            shutil.rmtree(self.job_dir,ignore_errors=True);self.job_dir=None

    def back(self):
        if self.running:self.after_job=None;self.grid_pending=False;self.stop_job();return
        if self.stack:
            self.current,items,index=self.stack.pop();self.show_items(items)
            self['list'].moveToIndex(index)
            self.selection_changed()
            self.maybe_grid()
        else:self.close()

    def cleanup(self):
        self.closed=True;self.timer.stop();self.stop_job()
        self.cover_timer.stop();self.stop_cover_fetch()
        callbacks=self.cover_decoder.PictureData.get()
        if self.cover_decoded in callbacks:callbacks.remove(self.cover_decoded)
        # Screen.doClose clears our state after onClose. Disconnect callbacks
        # now so a finishing worker cannot call into the destroyed screen.
        if self.container is not None:
            for event,callback in [(self.container.dataAvail,self.data),(self.container.appClosed,self.finished)]:
                if callback in event:event.remove(callback)
        self.running=False
        self.release_job()


def main(session,**kwargs):session.open(MKEkino)


def Plugins(**kwargs):
    return [PluginDescriptor(name='MK Kino',description='Filmy i seriale — samodzielna wtyczka MK',
                             where=PluginDescriptor.WHERE_PLUGINMENU,icon='icon.png',fnc=main)]
