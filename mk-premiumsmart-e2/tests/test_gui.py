import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/MKPremiumSmartE2'))


def load_ui():
    class Screen(dict):
        def __init__(self,session):
            self.session=session;self.onLayoutFinish=[];self.onClose=[]
        def close(self,*args):pass
        def doClose(self):
            # Screen.doClose uses dict.items() after running onClose callbacks.
            for method in self.onClose:method()
            for name,value in list(self.items()):del self[name]
            self.__dict__.clear()
        def createGUIScreen(self):
            # Exact layout callback dispatch from OpenATV 26c24da Screen.py.
            # https://github.com/openatv/enigma2/blob/26c24da/lib/python/Screens/Screen.py
            for method in self.onLayoutFinish:
                if not isinstance(method,type(self.close)):
                    exec(method,globals(),locals())
                else:
                    method()
    class Label:
        def __init__(self,text=''):self.text=text;self.visible=True
        def setText(self,text):self.text=text
        def show(self):self.visible=True
        def hide(self):self.visible=False
        def pageUp(self):pass
        def pageDown(self):pass
    class Menu:
        def __init__(self,values):self.values=values;self.index=0;self.onSelectionChanged=[]
        def setList(self,values):self.values=values;self.index=min(self.index,max(0,len(values)-1))
        def getCurrent(self):return self.values[self.index] if self.values else None
        def getSelectedIndex(self):return self.index
        def moveToIndex(self,index):self.index=index
    class Container:
        def __init__(self):self.dataAvail=[];self.appClosed=[];self.interrupts=0
        def execute(self,*args):self.args=args;return 0
        def sendCtrlC(self):self.interrupts+=1
    class Timer:
        def __init__(self):self.callback=[];self.starts=[]
        def start(self,*args):self.starts.append(args)
        def stop(self):pass
    class Ref:
        def __init__(self,*args):self.args=args
        def setName(self,name):self.name=name
    class Actions:
        def __init__(self,contexts,actions,priority=0):self.contexts=contexts;self.actions=actions;self.priority=priority
    class Player(Screen):
        SEEK_STATE_PLAY=(0,0,0,'play')
        SEEK_STATE_PAUSE=(1,0,0,'pause')
        def __init__(self,session,service,**kwargs):
            Screen.__init__(self,session);self.service=service;self.leave_count=0;self.shown=True
            self.seekstate=self.SEEK_STATE_PLAY;self.pause_count=0;self.unpause_count=0
        def leavePlayer(self):self.leave_count+=1
        def pauseService(self):self.pause_count+=1;self.seekstate=self.SEEK_STATE_PAUSE
        def unPauseService(self):self.unpause_count+=1;self.seekstate=self.SEEK_STATE_PLAY
        def show(self):self.shown=True
    class Picture:
        def __init__(self):self.instance=Mock();self.visible=True
        def hide(self):self.visible=False
        def show(self):self.visible=True
        def getSize(self):return 136,204
    class PicLoad:
        def __init__(self):self.callbacks=[];self.PictureData=types.SimpleNamespace(get=lambda:self.callbacks)
        def setPara(self,params):self.params=params
        def startDecode(self,path):self.path=path;return 0
        def getData(self):return 'decoded-picture'
    modules={
        'keymapparser':{'readKeymap':Mock()},
        'Components.ActionMap':{'ActionMap':Actions},
        'Components.Label':{'Label':Label},'Components.MenuList':{'MenuList':Menu},
        'Components.ScrollLabel':{'ScrollLabel':Label},
        'Components.Pixmap':{'Pixmap':Picture},
        'Plugins.Plugin':{'PluginDescriptor':Mock()},'Screens.Screen':{'Screen':Screen},
        'Screens.ChoiceBox':{'ChoiceBox':type('ChoiceBox',(),{})},
        'Screens.InfoBar':{'MoviePlayer':Player},
        'Screens.MessageBox':{'MessageBox':type('MessageBox',(),{'TYPE_ERROR':1,'TYPE_YESNO':2,'TYPE_INFO':3})},
        'Screens.VirtualKeyBoard':{'VirtualKeyBoard':type('VirtualKeyBoard',(),{})},
        'enigma':{'eTimer':Timer,'eServiceReference':Ref,'eConsoleAppContainer':Container,'ePicLoad':PicLoad}}
    for name,attrs in modules.items():
        mod=types.ModuleType(name);mod.__dict__.update(attrs);sys.modules[name]=mod
    spec=importlib.util.spec_from_file_location('mk_premiumsmart_plugin_test',ROOT/'src/MKPremiumSmartE2/plugin.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.ui=load_ui();self.session=Mock()
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.ui.watchstate.PATH=Path(self.temporary.name)/'library.json'
        self.screen=self.ui.MKPremiumSmart(self.session)
        self.addCleanup(self.finish)
    def finish(self):
        self.screen.running=False;self.screen.release_job()

    def test_openatv_74_layout_dispatch_starts_initial_catalogue(self):
        self.screen.createGUIScreen()
        self.assertEqual(self.screen.timer.starts,[(150,True)])
        for callback in self.screen.timer.callback:callback()
        request=json.loads((self.screen.job_dir/'request.json').read_text())
        self.assertEqual(request['item']['action'],'main')
        self.assertTrue(self.screen.running)

    def test_screen_close_retains_dictionary_items_method(self):
        screen=self.ui.MKPremiumSmart(self.session)
        self.assertTrue(callable(screen.items))
        screen.doClose()
        self.assertEqual(screen.__dict__,{})

    def test_cleanup_disconnects_worker_before_screen_destroys_its_state(self):
        screen=self.ui.MKPremiumSmart(self.session)
        screen.load({'action':'resolve','url':'https://premiumsmart.eu/api/v1/titles/123','provider':'player'})
        container=screen.container
        screen.cleanup()
        screen.__dict__.clear()  # Screen.doClose clears this after onClose.
        self.assertEqual(container.interrupts,1)
        self.assertEqual(container.dataAvail,[])
        self.assertEqual(container.appClosed,[])

    def test_quality_selection_writes_control_json_without_console_stdin(self):
        self.screen.load({'action':'resolve','url':'https://premiumsmart.eu/api/v1/titles/123','provider':'player'})
        container=self.screen.container
        self.screen.variant_selected(('Polski',1))
        self.assertEqual(json.loads((self.screen.job_dir/'control.json').read_text()),{'index':1})
        self.assertNotIn('write',vars(container))
        self.assertEqual(container.interrupts,0)

    def test_movie_waits_for_source_ok_even_with_saved_auto_preference(self):
        self.screen.preferences['auto_play']=True
        source={'action':'resolve','title':'Byse','provider':'byse','url':'https://premiumsmart.eu/api/v1/titles/123'}
        self.screen.load({'action':'sources','title':'Film','url':source['url']})
        (self.screen.job_dir/'result.json').write_text(json.dumps({'items':[source]}))
        self.screen.data('{"stage":"catalogue_ready"}\n')
        self.assertIsNone(self.screen.after_job)
        self.screen.finished(0)
        self.assertFalse(self.screen.running)
        self.session.openWithCallback.assert_not_called()
        self.screen['actions'].actions['ok']()
        request=json.loads((self.screen.job_dir/'request.json').read_text())
        self.assertEqual(request['item']['action'],'resolve')
        self.assertTrue(request['item']['auto_quality'])

    def test_repeated_cancel_interrupts_worker_once(self):
        self.screen.load({'action':'resolve','url':'https://premiumsmart.eu/api/v1/titles/123','provider':'player'})
        container=self.screen.container
        self.screen.variant_selected(None);self.screen.back()
        self.assertEqual(container.interrupts,1)
        self.screen.finished(130)
        self.assertIsNone(self.screen.job_dir)

    def test_native_player_accepts_only_loopback_and_stops_worker_on_close(self):
        self.screen.load({'action':'resolve','url':'https://premiumsmart.eu/api/v1/titles/123','provider':'player','movie_title':'Example'})
        container=self.screen.container
        self.screen.play('http://127.0.0.1:45000/token/master.m3u8')
        args=self.session.openWithCallback.call_args.args
        self.assertIs(args[1],self.ui.PremiumSmartMoviePlayer)
        self.assertEqual(args[2].args[0],4097)
        self.assertFalse(self.session.openWithCallback.call_args.kwargs['fromMovieSelection'])
        self.assertEqual(self.session.openWithCallback.call_args.kwargs['mk_resume'],0)
        self.screen.movie_closed()
        self.assertEqual(container.interrupts,1)

    def test_exit_stops_movie_on_release_even_with_infobar_visible(self):
        for shown in (True,False):
            player=self.ui.PremiumSmartMoviePlayer(self.session,'service',fromMovieSelection=False)
            player.shown=shown
            self.assertEqual(player.leavePlayerOnExit(),1)  # KEY_EXIT make, OpenATV MoviePlayerActions.
            self.assertEqual(player.leave_count,0)
            actions=player['mkExitActions']
            self.assertLess(actions.priority,0)
            actions.actions['cancel']()  # KEY_EXIT break, OkCancelActions.
            self.assertEqual(player.leave_count,1)
            actions.actions['hide']()  # Duplicate mappings cannot close twice.
            self.assertEqual(player.leave_count,1)

    def test_ok_make_and_break_pause_once_and_second_press_resumes(self):
        player=self.ui.PremiumSmartMoviePlayer(self.session,'service',fromMovieSelection=False)
        actions=player['mkPauseActions']
        self.assertLess(actions.priority,player['mkExitActions'].priority)
        # OpenATV 26c24da data/keymap.xml: make -> ok/unPauseService;
        # break -> OK/toggleShow. eActionMap stops dispatch on return 1.
        for make,release in [('ok','toggleShow'),('unPauseService','OK')]:
            self.assertEqual(actions.actions[make](),1)
            actions.actions[release]()
        self.assertEqual(player.pause_count,1);self.assertEqual(player.unpause_count,1)
        self.assertEqual(player.seekstate,player.SEEK_STATE_PLAY)
        player.mk_cleanup()

    def test_ok_uses_native_pause_state_and_does_not_interfere_with_closing(self):
        player=self.ui.PremiumSmartMoviePlayer(self.session,'service',fromMovieSelection=False)
        player.pauseService()  # A dedicated PAUSE key changed the native state.
        player['mkPauseActions'].actions['OK']()
        self.assertEqual(player.unpause_count,1)
        player.mk_leaving=True;player['mkPauseActions'].actions['OK']()
        self.assertEqual(player.pause_count,1);player.mk_cleanup()

    def test_contact_is_in_options_and_qr_decoder_is_detached_on_close(self):
        self.screen.options()
        choices=self.session.openWithCallback.call_args.kwargs['list']
        self.assertIn(('Autor i kontakt','contact'),choices)
        self.screen.option_selected(('Autor i kontakt','contact'))
        self.session.open.assert_called_with(self.ui.Contact)
        contact=self.ui.Contact(self.session);contact.createGUIScreen()
        self.assertIn('contact_qr.png',contact.decoder.path)
        self.assertEqual(contact['email'].text,'bimer55@wp.pl')
        self.assertIn('MK',contact['author'].text)
        decoder=contact.decoder;contact.doClose()
        self.assertEqual(decoder.callbacks,[])

    def test_ratings_are_visible_without_changing_title_passed_to_player(self):
        entry={'title':'Example','action':'sources','rating':8.5,'rating_votes':3,'rating_label':'Ekino: 8,5/10 · głosów: 3'}
        self.screen.show_items([entry])
        shown,data=self.screen['list'].getCurrent()
        self.assertEqual(shown,'[8,5/10] Example');self.assertEqual(data['title'],'Example')

    def test_blue_opens_updater_and_info_opens_notices(self):
        self.screen['actions'].actions['blue']()
        self.session.open.assert_called_with(self.ui.Updates)
        self.screen['actions'].actions['info']()
        self.session.open.assert_called_with(self.ui.Notices)

    def test_update_checks_off_ui_thread_and_requires_install_choice(self):
        screen=self.ui.Updates(self.session);screen.createGUIScreen()
        for callback in screen.timer.callback:callback()
        self.assertIn('updater.py',screen.container.args[3])
        self.assertNotIn('--install',screen.container.args)
        screen.data(json.dumps({'status':'available','version':'0.2.0','sha256':'a'*64,'notes':'New release'})+'\n')
        screen.finished(0)
        self.assertIn('0.2.0',screen['text'].text)
        screen.confirm()
        self.assertFalse(screen.busy)
        callback=self.session.openWithCallback.call_args.args[0]
        callback(True)
        self.assertTrue(screen.installing);self.assertIn('--install',screen.container.args)
        screen.close=Mock();screen.back();screen.close.assert_not_called()
        screen.data(json.dumps({'status':'installed','version':'0.2.0'})+'\n');screen.finished(0)
        self.assertTrue(screen.restart_needed)
        screen.cleanup()

    def test_update_close_disconnects_check_callbacks_before_screen_destruction(self):
        screen=self.ui.Updates(self.session);screen.check();container=screen.container
        screen.doClose()
        self.assertEqual(container.interrupts,1)
        self.assertEqual(container.dataAvail,[]);self.assertEqual(container.appClosed,[])
        self.assertEqual(screen.__dict__,{})

    def test_late_quality_callback_after_cancel_is_ignored(self):
        self.screen.load({'action':'resolve','url':'https://premiumsmart.eu/api/v1/titles/123','provider':'player'})
        self.screen.stop_job();self.screen.variant_selected(('Polski',0))
        self.assertFalse((self.screen.job_dir/'control.json').exists())

    def test_new_list_starts_at_top_but_exit_restores_parent_selection(self):
        entries=[{'title':'Item '+str(i),'action':'sources'} for i in range(6)]
        self.screen.show_items(entries);self.screen['list'].moveToIndex(5)
        self.screen.stack.append((self.screen.current,entries,5))
        self.screen.show_items(entries)
        self.assertEqual(self.screen['list'].getSelectedIndex(),0)
        self.screen.back()
        self.assertEqual(self.screen['list'].getSelectedIndex(),5)

    def test_poster_download_does_not_start_catalogue_worker_or_block_selection(self):
        entry={'title':'Film','action':'sources','icon':'https://ekino.ws/static/thumb/test.jpg'}
        self.screen.show_items([entry])
        self.assertFalse(self.screen.running);self.assertIsNone(self.screen.container)
        self.assertEqual(self.screen.cover_timer.starts[-1],(250,True))
        self.screen.request_cover();process=self.screen.cover_process
        self.assertIn('poster.py',process.args[2])
        self.screen.show_items([{'title':'Other','action':'sources'}])
        self.screen.cover_fetched(0)
        self.assertFalse(self.screen['poster'].visible)

    def test_late_poster_decode_does_not_show_previous_film_cover(self):
        self.screen.cover_url='https://ekino.ws/static/thumb/first.jpg'
        self.screen['poster'].getSize=lambda:(204,306)
        self.screen.decode_cover(Path('/tmp/example.jpg'))
        self.assertEqual(self.screen.cover_decoder.params[:2],(204,306))
        self.screen.cover_url='https://ekino.ws/static/thumb/second.jpg'
        self.screen['poster'].hide();self.screen.cover_decoded()
        self.assertFalse(self.screen['poster'].visible)
        self.screen.decode_cover(Path('/tmp/second.jpg'));self.screen.cover_decoded()
        self.assertTrue(self.screen['poster'].visible)

    def test_close_disconnects_poster_fetch_and_decoder(self):
        self.screen.cover_url='https://ekino.ws/static/thumb/example.jpg';self.screen.request_cover()
        process=self.screen.cover_process;decoder=self.screen.cover_decoder
        self.screen.cleanup()
        self.assertEqual(process.interrupts,1)
        self.assertEqual(process.appClosed,[]);self.assertEqual(decoder.callbacks,[])


if __name__=='__main__':unittest.main()
