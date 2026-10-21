"""Remote-controlled playback experiment; no Kodi or E2iPlayer imports."""
import json
import os
import sys
from pathlib import Path

from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.ProgressBar import ProgressBar
from Components.ScrollLabel import ScrollLabel
from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from enigma import eConsoleAppContainer, eTimer
from .version import APP_NAME, APP_VERSION
from .epg_ui import EpgLoader, programme_line, programme_details, programme_progress

ROOT = Path(__file__).resolve().parent

STAGES = {
    "vod_check_access": "Sprawdzanie sesji CANAL+...",
    "vod_resolve_stream": "Sprawdzanie dostępu do filmu lub odcinka...",
    "vod_ended": "Koniec materiału.",
    "prepare": "Przygotowanie odtwarzacza...",
    "prepare_player": "Pierwsze uruchomienie: pobieranie odtwarzacza (11 MB)...",
    "refresh_channels": "Sprawdzanie sesji i dostepu do kanalu...",
    "resolve_stream": "Pobieranie strumienia...",
    "inspect_initialization": "Sprawdzanie sciezek obrazu i dzwieku...",
    "license": "Uzyskiwanie licencji dla obrazu i dzwieku...",
    "key_mapping": "Sprawdzanie dopasowania licencji do sciezek...",
    "check_video_quality": "Sprawdzanie jakosci objetych otrzymana licencja...",
    "quality_selected": "Wybrano najwyzsza jakosc objeta otrzymana licencja.",
    "license_ok": "Licencja przyjeta. Uruchamianie obrazu...",
    "starting_player": "Otwieranie odtwarzacza...",
    "player_running": "Odtwarzacz uruchomiony. Sprawdz obraz i dzwiek. EXIT: powrot.",
    "stopped": "Odtwarzanie zatrzymane.",
}


class CanalE2NowNext(Screen):
    skin = """<screen name="CanalE2NowNext" position="center,center" size="1000,580" title="MK Canal+ E2 — Teraz / Następnie">
      <widget name="body" position="30,25" size="940,465" font="Regular;25" />
      <widget name="hint" position="30,510" size="940,40" font="Regular;21" />
    </screen>"""

    def __init__(self, session, channel_name, data):
        Screen.__init__(self, session)
        paragraphs = [channel_name, ""]
        for key, heading in (("current", "TERAZ"), ("next", "NASTĘPNIE")):
            programme = data.get(key)
            paragraphs += [heading, programme_line(programme),
                           programme_details(programme) or ("Brak opisu w danych CANAL+." if programme else ""), ""]
        self["body"] = ScrollLabel("\n".join(paragraphs))
        self["hint"] = Label("Źródło: CANAL+  ·  ↑/↓: przewijanie  ·  OK / EXIT: Wróć")
        self["actions"] = ActionMap(["OkCancelActions", "DirectionActions"], {
            "ok": self.close, "cancel": self.close,
            "up": self["body"].pageUp, "down": self["body"].pageDown}, -2)


class CanalE2Player(Screen):
    skin = """<screen name="CanalE2Player" position="0,0" size="1280,720" flags="wfNoBorder" backgroundColor="transparent" zPosition="5">
      <widget name="status" position="40,510" size="1200,170" font="Regular;23" foregroundColor="white" backgroundColor="#50000000" transparent="0" />
    </screen>"""

    def __init__(self, session, channel_id, channel_name, vod=False, description=""):
        Screen.__init__(self, session)
        self.channel_id, self.channel_name = channel_id, channel_name
        self.vod, self.description, self.paused, self.ended = vod, description, False, False
        self.control_pending = False
        self.actual_height = None
        self.epg = {}
        self.playing_started = False
        self["status"] = Label(channel_name + "\nPrzygotowanie...")
        self["actions"] = ActionMap(["OkCancelActions", "InfobarActions", "InfoActions", "InfobarEPGActions",
                                    "ColorActions", "DirectionActions"], {
            "cancel": self.stop, "ok": self.toggle_status, "showMovies": self.toggle_status,
            "info": self.show_programmes, "InfoPressed": self.show_programmes,
            "EPGPressed": self.show_programmes, "green": self.pause_resume,
            "left": lambda: self.control("seek_back"),
            "right": lambda: self.control("seek_forward")}, -2)
        self.epg_loader = EpgLoader(self.epg_received)
        if not self.vod:
            self.epg_loader.request(channel_id)
        self.onShow.append(self.epg_loader.resume)
        self.onHide.append(self.epg_loader.pause)
        self.previous = session.nav.getCurrentlyPlayingServiceReference()
        self.container = None
        self.buffer = ""
        self.running, self.stopping, self.closed = False, False, False
        self.status_visible = True
        self.status_timer = eTimer()
        self.status_timer.callback.append(self.hide_status)
        self.start_timer = eTimer()
        self.start_timer.callback.append(self.start)
        self.onClose.append(self.cleanup)
        self.onFirstExecBegin.append(lambda: self.start_timer.start(100, True))

    def start(self):
        if self.stopping or self.closed or self.container is not None:
            return
        self.session.nav.stopService()
        self.container = eConsoleAppContainer()
        self.container.dataAvail.append(self.on_data)
        self.container.appClosed.append(self.on_exit)
        python = "/usr/bin/python3"
        worker = str(ROOT / "playback_worker.py")
        self.running = True
        result = self.container.execute(python, python, "-u", worker,
                                        "--vod" if self.vod else "--channel", self.channel_id, "--height", "1080")
        if result:
            self.running = False
            self["status"].setText("Nie mozna uruchomic testu. EXIT: powrot.")

    def on_data(self, data):
        if self.closed:
            return
        text = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
        self.buffer = (self.buffer + text)[-65536:]
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            try:
                event = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(event, dict):
                continue
            stage = event.get("stage")
            height = event.get("selected_video_height")
            if isinstance(height, int) and 0 < height <= 4320:
                self.actual_height = height
            if stage == "error":
                self.playing_started = False
                reason = event.get("reason", "error")
                # Worker reasons are codes, never native player exception text.
                message = "Blad: %s\nRaport: /tmp/canal_e2_playback_report.json\nEXIT: powrot." % reason
                self.status_timer.stop()
                self["status"].show()
                self.status_visible = True
            else:
                message = STAGES.get(stage)
            if message:
                quality = " — %dp" % self.actual_height if self.actual_height else ""
                self["status"].setText(self.channel_name + quality + "\n" + message)
            if stage == "player_running":
                self.playing_started = True
                self.update_overlay()
                self.status_timer.start(7000, True)
            elif stage == "vod_ended":
                self.ended = True
            elif stage in ("vod_paused", "vod_resumed", "vod_control_failed"):
                self.control_pending = False
                if stage != "vod_control_failed":
                    self.paused = stage == "vod_paused"
                self.update_overlay()
                self["status"].show()
                self.status_visible = True
                self.status_timer.stop()
                if stage == "vod_control_failed":
                    self["status"].setText(self.channel_name + "\nOdtwarzacz nie wykonał tej operacji.\nEXIT: powrót")
                if not self.paused:
                    self.status_timer.start(5000, True)

    def epg_received(self, event):
        self.epg = event if event.get("stage") == "epg_loaded" else {}
        if self.playing_started and not self.closed:
            self.update_overlay()

    def update_overlay(self):
        quality = " — %dp" % self.actual_height if self.actual_height else ""
        if self.vod:
            self["status"].setText(self.channel_name + quality
                + ("\nPauza" if self.paused else "\nOdtwarzanie VOD")
                + "\nZIELONY: pauza / odtwarzaj  ·  ←/→: 30 sekund"
                + "\nOK: pokaż/ukryj  ·  INFO: opis  ·  EXIT: powrót")
            return
        self["status"].setText(self.channel_name + quality + "\nTeraz: "
            + programme_line(self.epg.get("current")) + "\nNastępnie: "
            + programme_line(self.epg.get("next"))
            + "\nOK: pokaż/ukryj  ·  INFO: szczegóły  ·  EXIT: powrót")

    def show_programmes(self):
        if self.vod:
            from .vod_ui import CanalVodDescription
            self.session.open(CanalVodDescription, self.channel_name, self.description)
        else:
            self.session.open(CanalE2NowNext, self.channel_name, self.epg)

    def control(self, command):
        if self.vod and self.playing_started and self.container is not None and self.running:
            self.container.write((command + "\n").encode("ascii"))

    def pause_resume(self):
        if not self.vod or not self.playing_started or self.control_pending:
            return
        self.control_pending = True
        self.control("resume" if self.paused else "pause")

    def hide_status(self):
        if not self.closed:
            self["status"].hide()
            self.status_visible = False

    def toggle_status(self):
        self.status_timer.stop()
        if self.status_visible:
            self["status"].hide()
        else:
            self["status"].show()
        self.status_visible = not self.status_visible

    def stop(self):
        if self.stopping:
            return
        self.stopping = True
        self.playing_started = False
        self.status_timer.stop()
        if self.container is not None and self.running:
            self["status"].show()
            self["status"].setText("Zatrzymywanie odtwarzacza...")
            self.container.sendCtrlC()
        else:
            self.close()

    def on_exit(self, code):
        self.running = False
        self.playing_started = False
        if self.closed:
            return
        if self.stopping or self.ended:
            self.close()
        elif code != 0:
            self.status_timer.stop()
            self["status"].show()
            try:
                report = json.loads(Path("/tmp/canal_e2_playback_report.json").read_text())
                reason = report.get("reason", "worker_exited")
            except (ValueError, OSError):
                reason = "worker_exited"
            self["status"].setText("Blad: %s\nRaport: /tmp/canal_e2_playback_report.json\nEXIT: powrot." % reason)

    def cleanup(self):
        self.closed = True
        self.epg_loader.close()
        self.start_timer.stop()
        self.status_timer.stop()
        if self.container is not None:
            if self.running:
                self.container.sendCtrlC()
            for signal, callback in ((self.container.dataAvail, self.on_data), (self.container.appClosed, self.on_exit)):
                if callback in signal:
                    signal.remove(callback)
        if self.previous is not None:
            self.session.nav.playService(self.previous)


class CanalE2Account(Screen):
    skin = """<screen name="CanalE2Account" position="center,center" size="1000,500" title="MK Canal+ E2 — logowanie">
      <widget name="message" position="35,35" size="930,140" font="Regular;27" />
      <widget name="code" position="35,185" size="930,110" font="Regular;60" halign="center" />
      <widget name="hint" position="35,330" size="930,110" font="Regular;23" />
    </screen>"""

    def __init__(self, session, mode="login"):
        Screen.__init__(self, session)
        self.mode = mode
        self["message"] = Label("Przygotowanie...")
        self["code"] = Label("")
        self["hint"] = Label("EXIT: anuluj i wroc do listy")
        self["actions"] = ActionMap(["OkCancelActions"], {"cancel": self.cancel}, -2)
        self.container = None
        self.buffer = ""
        self.running, self.stopping, self.success, self.closed = False, False, False, False
        self.timer = eTimer()
        self.timer.callback.append(self.start)
        self.onFirstExecBegin.append(lambda: self.timer.start(100, True))
        self.onClose.append(self.cleanup)

    def start(self):
        if self.container is not None or self.closed or self.stopping:
            return
        self.container = eConsoleAppContainer()
        self.container.dataAvail.append(self.data)
        self.container.appClosed.append(self.finished)
        self.running = True
        python = "/usr/bin/python3"
        result = self.container.execute(python, python, "-u", str(ROOT / "account_worker.py"), self.mode)
        if result:
            self.running = False
            self["message"].setText("Nie mozna uruchomic logowania. EXIT: powrot.")

    def data(self, data):
        if self.closed:
            return
        text = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
        self.buffer = (self.buffer + text)[-65536:]
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            try:
                event = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(event, dict):
                continue
            stage = event.get("stage")
            if stage == "pairing_code":
                code = event.get("activation_code", "")
                if isinstance(code, str) and len(code) <= 128 and all(c.isalnum() or c in "-_ " for c in code):
                    self["message"].setText("Otworz na telefonie:\nhttps://connect.canalplus.com/\nZaloguj sie i zatwierdz kod:")
                    self["code"].setText(code)
            elif stage == "authenticated":
                self["code"].setText("")
                self["message"].setText("Logowanie potwierdzone. Pobieranie kanalow...")
            elif stage == "generate_code":
                self["message"].setText("Pobieranie kodu logowania...")
            elif stage == "refresh_channels":
                self["message"].setText("Pobieranie kanalow z Twojej subskrypcji...")
            elif stage == "channels_loaded":
                self.success = True
                self["message"].setText("Lista kanalow gotowa.")
            elif stage == "login_required":
                self["message"].setText("Brak zapisanej sesji. Wroc i wybierz zielony przycisk: Zaloguj.")
            elif stage == "error":
                self["code"].setText("")
                self["message"].setText("Blad: %s\nEXIT: powrot. Logowanie mozna ponowic zielonym przyciskiem." % event.get("reason", "error"))

    def finished(self, code):
        self.running = False
        if not self.closed and (self.success or self.stopping):
            self.close(self.success)

    def cancel(self):
        self.stopping = True
        self["code"].setText("")
        if self.container is not None and self.running:
            self["message"].setText("Anulowanie...")
            self.container.sendCtrlC()
        else:
            self.close(False)

    def cleanup(self):
        self.closed = True
        self.timer.stop()
        self.buffer = ""
        if self.container is not None:
            if self.running:
                self.container.sendCtrlC()
            for signal, callback in ((self.container.dataAvail, self.data), (self.container.appClosed, self.finished)):
                if callback in signal:
                    signal.remove(callback)


class CanalE2Update(Screen):
    skin = """<screen name="CanalE2Update" position="center,center" size="1000,520" title="MK Canal+ E2 — aktualizacja">
      <widget name="message" position="30,30" size="940,125" font="Regular;28" />
      <widget name="notes" position="30,175" size="940,230" font="Regular;22" />
      <widget name="key_red" position="30,445" size="300,44" font="Regular;23" halign="center" valign="center" foregroundColor="white" backgroundColor="#a42c35" />
      <widget name="key_green" position="350,445" size="610,44" font="Regular;23" halign="center" valign="center" foregroundColor="white" backgroundColor="#177443" />
    </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self["message"] = Label("Sprawdzanie aktualizacji na GitHubie...")
        self["notes"] = Label("Zainstalowana wersja: " + APP_VERSION)
        self["key_red"] = Label("Wróć")
        self["key_green"] = Label("")
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "cancel": self.cancel, "red": self.cancel, "green": self.confirm, "ok": self.confirm}, -2)
        self.container = None
        self.buffer = ""
        self.running = self.installing = self.stopping = self.closed = self.restart_ready = False
        self.latest = None
        self.timer = eTimer()
        self.timer.callback.append(self.start_check)
        self.onFirstExecBegin.append(lambda: self.timer.start(100, True))
        self.onClose.append(self.cleanup)

    def start_check(self):
        self.start("check")

    def start(self, mode):
        if self.running or self.closed:
            return
        self.detach()
        self.buffer = ""
        self.container = eConsoleAppContainer()
        self.container.dataAvail.append(self.data)
        self.container.appClosed.append(self.finished)
        self.running = True
        self["key_green"].setText("")
        python = "/usr/bin/python3"
        arguments = [python, python, "-u", str(ROOT / "update_worker.py"), mode]
        if mode == "install":
            arguments.extend(["--expected-version", self.latest])
        result = self.container.execute(*arguments)
        if result:
            self.running = False
            self["message"].setText("Nie można uruchomić aktualizacji.")

    def data(self, data):
        if self.closed:
            return
        text = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
        self.buffer = (self.buffer + text)[-65536:]
        errors = {
            "update_connection_or_tls_error": "Brak połączenia z GitHubem. Spróbuj ponownie później.",
            "update_file_not_found": "Nie znaleziono pliku aktualizacji na GitHubie.",
            "update_checksum_mismatch": "Plik jest niekompletny lub uszkodzony. Nie został zainstalowany.",
            "update_changed_check_again": "Pojawiła się inna wersja. Sprawdź aktualizacje ponownie.",
            "opkg_install_failed": "Instalator zgłosił błąd. Aktualizacja nie została potwierdzona.",
            "installed_version_not_confirmed": "Nie potwierdzono nowej wersji. Wróć, zrestartuj interfejs Enigma2 i sprawdź numer wersji wtyczki.",
        }
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            try:
                event = json.loads(line)
            except (ValueError, TypeError):
                continue
            if not isinstance(event, dict):
                continue
            stage = event.get("stage")
            if stage == "update_available":
                self.latest = event.get("version")
                self["message"].setText("Dostępna wersja: %s\nTwoja wersja: %s" % (self.latest, APP_VERSION))
                self["notes"].setText(event.get("notes", ""))
                self["key_green"].setText("Zainstaluj aktualizację")
            elif stage == "up_to_date":
                self.latest = None
                installed_version = str(event.get("version", APP_VERSION))
                self["message"].setText("Masz aktualną wersję: " + installed_version)
                self["notes"].setText("Nowe wersje MK Canal+ E2 będą dostępne w tym miejscu.")
                if installed_version != APP_VERSION:
                    self.restart_ready = True
                    self["key_green"].setText("Uruchom ponownie interfejs")
                    self["notes"].setText("Nowa wersja jest zainstalowana. Zrestartuj interfejs, aby ją załadować.")
            elif stage == "downloading":
                self["message"].setText("Pobieranie i sprawdzanie pakietu...")
            elif stage == "installing":
                self.installing = True
                self["key_red"].setText("")
                self["message"].setText("Trwa instalacja. Poczekaj na zakończenie.")
            elif stage == "installed":
                self.installing = False
                self.restart_ready = True
                self["key_red"].setText("Później")
                self["key_green"].setText("Uruchom ponownie interfejs")
                self["message"].setText("Zainstalowano wersję " + str(event.get("version", "")))
                self["notes"].setText("Logowanie zostało zachowane. Zrestartuj interfejs, aby załadować nową wersję.")
            elif stage == "error":
                self.installing = False
                self["key_red"].setText("Wróć")
                reason = event.get("reason", "error")
                self["message"].setText(errors.get(reason, "Błąd aktualizacji: " + str(reason)))

    def confirm(self):
        if self.running or self.installing:
            return
        if self.restart_ready:
            from Screens.Standby import TryQuitMainloop
            self.session.open(TryQuitMainloop, 3)
        elif self.latest:
            self.start("install")

    def finished(self, code):
        self.running = False
        self.installing = False
        if self.stopping and not self.closed:
            self.close()

    def cancel(self):
        if self.installing:
            return
        if self.running:
            self.stopping = True
            self.container.sendCtrlC()
        else:
            self.close()

    def detach(self):
        if self.container is not None:
            for signal, callback in ((self.container.dataAvail, self.data), (self.container.appClosed, self.finished)):
                if callback in signal:
                    signal.remove(callback)

    def cleanup(self):
        self.closed = True
        self.timer.stop()
        if self.running and not self.installing and self.container is not None:
            self.container.sendCtrlC()
        self.detach()


class CanalE2Channels(Screen):
    skin = """<screen name="CanalE2Channels" position="center,center" size="1000,640" title="MK Canal+ E2">
      <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/CanalE2Test/logo.png" position="25,16" size="128,128" alphatest="blend" />
      <widget name="brand" position="175,38" size="800,40" font="Regular;31" />
      <widget name="creator" position="175,91" size="800,29" font="Regular;20" foregroundColor="#bcbcbc" />
      <widget name="channels" position="25,160" size="390,365" scrollbarMode="showOnDemand" />
      <eLabel text="TERAZ" position="440,158" size="535,28" font="Regular;20" foregroundColor="#6fcbff" />
      <widget name="now_title" position="440,190" size="535,64" font="Regular;24" />
      <widget name="now_details" position="440,258" size="535,48" font="Regular;20" foregroundColor="#c8c8c8" />
      <widget name="epg_progress" position="440,316" size="535,8" foregroundColor="#6fcbff" backgroundColor="#363636" />
      <eLabel text="NASTĘPNIE" position="440,345" size="535,28" font="Regular;20" foregroundColor="#6fcbff" />
      <widget name="next_title" position="440,377" size="535,64" font="Regular;24" />
      <widget name="next_details" position="440,445" size="535,48" font="Regular;20" foregroundColor="#c8c8c8" />
      <widget name="epg_source" position="440,501" size="535,24" font="Regular;18" foregroundColor="#aaaaaa" />
      <widget name="hint" position="25,532" size="950,30" font="Regular;22" />
      <widget name="key_green" position="25,578" size="300,40" font="Regular;22" halign="center" valign="center" foregroundColor="white" backgroundColor="#177443" />
      <widget name="key_yellow" position="345,578" size="300,40" font="Regular;22" halign="center" valign="center" foregroundColor="black" backgroundColor="#e3bc38" />
      <widget name="key_blue" position="665,578" size="310,40" font="Regular;22" halign="center" valign="center" foregroundColor="white" backgroundColor="#2363ba" />
    </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self["channels"] = MenuList([])
        self["brand"] = Label(APP_NAME)
        self["creator"] = Label("Pomysł i projekt: MK  ·  Wersja " + APP_VERSION)
        self["hint"] = Label("")
        self["key_green"] = Label("Zaloguj")
        self["key_yellow"] = Label("Odśwież kanały")
        self["key_blue"] = Label("Aktualizacja")
        self["now_title"] = Label("Wybierz kanał")
        self["now_details"] = Label("")
        self["next_title"] = Label("")
        self["next_details"] = Label("")
        self["epg_source"] = Label("EPG: CANAL+")
        self["epg_progress"] = ProgressBar()
        self["epg_progress"].setRange((0, 100))
        self.epg = {}
        self.epg_channel = None
        self.epg_loader = EpgLoader(self.epg_received)
        self["channels"].onSelectionChanged.append(self.selection_changed)
        self.onShow.append(self.epg_loader.resume)
        self.onHide.append(self.epg_loader.pause)
        self.onClose.append(self.cleanup_epg)
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "InfoActions", "InfobarEPGActions"], {
            "ok": self.play, "cancel": self.close, "green": self.login, "yellow": self.refresh,
            "blue": self.update, "info": self.show_programmes, "InfoPressed": self.show_programmes,
            "EPGPressed": self.show_programmes}, -2)
        self.reload()
        if not self.entries and Path("/etc/canal-e2/session.json").is_file():
            self.onFirstExecBegin.append(self.refresh)

    def reload(self, *args):
        entries = []
        try:
            data = json.loads(Path("/etc/canal-e2/live.json").read_text())
            for item in data.get("channels", []):
                if item.get("authorized") is True:
                    entries.append((str(item.get("name", "Kanal")), str(item["epg_id"])))
        except (OSError, ValueError, KeyError, TypeError):
            pass
        self.entries = entries
        self["channels"].setList(entries)
        self["hint"].setText("OK: Odtwarzaj  ·  INFO: Teraz / Następnie  ·  EXIT: Wróć" if entries else
                             "OK lub zielony przycisk: Zaloguj kodem  ·  EXIT: Wróć")
        self.selection_changed()

    def selection_changed(self):
        item = self["channels"].getCurrent()
        channel = item[1] if item is not None else None
        if channel != self.epg_channel:
            self.epg = {}
            self.epg_channel = channel
            self["now_title"].setText("Pobieranie danych..." if channel else "Wybierz kanał")
            self["next_title"].setText("")
            self["now_details"].setText("")
            self["next_details"].setText("")
            self["epg_progress"].setValue(0)
            self["epg_source"].setText("EPG: CANAL+")
        self.epg_loader.request(channel)

    def epg_received(self, event):
        if event.get("channel_id") != self.epg_channel:
            return
        self.epg = event if event.get("stage") == "epg_loaded" else {}
        for prefix, key in (("now", "current"), ("next", "next")):
            programme = self.epg.get(key)
            self[prefix + "_title"].setText(programme_line(programme))
            self[prefix + "_details"].setText(programme_details(programme))
        self["epg_progress"].setValue(programme_progress(self.epg.get("current")))
        source = "EPG: CANAL+"
        if self.epg.get("cached"):
            source += " · zapisane dane"
        elif not self.epg:
            source += " · chwilowo niedostępne"
        self["epg_source"].setText(source)

    def show_programmes(self):
        item = self["channels"].getCurrent()
        if item is not None:
            self.session.open(CanalE2NowNext, item[0], self.epg)

    def cleanup_epg(self):
        self.epg_loader.close()
        if self.selection_changed in self["channels"].onSelectionChanged:
            self["channels"].onSelectionChanged.remove(self.selection_changed)

    def login(self):
        self.session.openWithCallback(self.reload, CanalE2Account, "login")

    def refresh(self):
        self.session.openWithCallback(self.reload, CanalE2Account, "refresh")

    def update(self):
        self.session.open(CanalE2Update)

    def play(self):
        item = self["channels"].getCurrent()
        if item is not None:
            self.session.open(CanalE2Player, item[1], item[0])
        else:
            self.login()


class CanalE2Home(Screen):
    skin = """<screen name="CanalE2Home" position="center,center" size="1000,640" title="MK Canal+ E2">
      <ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/CanalE2Test/logo.png" position="25,16" size="128,128" alphatest="blend" />
      <widget name="brand" position="175,38" size="800,40" font="Regular;31" />
      <widget name="creator" position="175,91" size="800,29" font="Regular;20" foregroundColor="#bcbcbc" />
      <widget name="sections" position="25,165" size="950,345" scrollbarMode="showOnDemand" />
      <widget name="hint" position="25,532" size="950,30" font="Regular;22" />
      <widget name="key_green" position="25,578" size="300,40" font="Regular;22" halign="center" backgroundColor="#177443" />
      <widget name="key_yellow" position="345,578" size="300,40" font="Regular;22" halign="center" foregroundColor="black" backgroundColor="#e3bc38" />
      <widget name="key_blue" position="665,578" size="310,40" font="Regular;22" halign="center" backgroundColor="#2363ba" />
    </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        from .vod_data import ROOTS
        self["brand"] = Label(APP_NAME)
        self["creator"] = Label("Pomysł i projekt: MK  ·  Wersja " + APP_VERSION)
        self["sections"] = MenuList([("Telewizja na żywo", "tv")]
                                   + [(title, path) for title, path in ROOTS] + [("Szukaj filmu / serialu", "search")])
        self["hint"] = Label("OK: Otwórz  ·  EXIT: Wróć")
        self["key_green"] = Label("Zaloguj")
        self["key_yellow"] = Label("Odśwież kanały")
        self["key_blue"] = Label("Aktualizacja")
        self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], {
            "ok": self.select, "cancel": self.close, "green": self.login,
            "yellow": self.refresh, "blue": self.update}, -2)

    def select(self):
        item = self["sections"].getCurrent()
        if not item:
            return
        if item[1] == "tv":
            self.session.open(CanalE2Channels)
        elif item[1] == "search":
            from Screens.VirtualKeyBoard import VirtualKeyBoard
            self.session.openWithCallback(self.search_received, VirtualKeyBoard,
                                          title="Szukaj filmu lub serialu w CANAL+", text="")
        else:
            from .vod_ui import CanalVodBrowser
            self.session.open(CanalVodBrowser, {"url": item[1]})

    def search_received(self, query):
        if isinstance(query, str) and query.strip():
            from .vod_ui import CanalVodBrowser
            self.session.open(CanalVodBrowser, query=query.strip()[:160])

    def login(self):
        self.session.open(CanalE2Account, "login")

    def refresh(self):
        self.session.open(CanalE2Account, "refresh")

    def update(self):
        self.session.open(CanalE2Update)


def main(session, **kwargs):
    session.open(CanalE2Home)


def Plugins(**kwargs):
    return [PluginDescriptor(name=APP_NAME, description="Projekt MK · telewizja, filmy, seriale i aktualizacje online",
                             icon=str(ROOT / "icon.png"), where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main)]
