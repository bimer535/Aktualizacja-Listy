# SPDX-License-Identifier: GPL-3.0-only
"""Visible time jumps and timeline selection for OpenPLi/OpenATV MoviePlayer."""
import time
from Screens.Screen import Screen
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from enigma import eTimer, getDesktop


def timecode(pts):
    if pts is None:
        return '--:--:--'
    seconds = max(0, int(pts) // PTS)
    return '%02d:%02d:%02d' % (seconds // 3600, seconds // 60 % 60, seconds % 60)


class SeekStatus(Screen):
    """Non-modal overlay: never takes remote focus from MoviePlayer."""
    def __init__(self, session):
        size = getDesktop(0).size()
        scale = size.width() / 1280.0
        w, h = int(1100 * scale), int(158 * scale)
        f = lambda n: int(n * scale)
        self.skin = ('<screen name="MKSeekStatus" position="%d,%d" size="%d,%d" '
                     'flags="wfNoBorder" backgroundColor="#101824" zPosition="20">'
                     '<widget name="mode" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="#25d6de" />'
                     '<widget name="position" position="%d,%d" size="%d,%d" font="Regular;%d" />'
                     '<widget name="progress" position="%d,%d" size="%d,%d" borderWidth="1" foregroundColor="#25d6de" />'
                     '<widget name="hint" position="%d,%d" size="%d,%d" font="Regular;%d" />'
                     '</screen>') % (
                         (size.width()-w)//2, size.height()-h-f(40), w, h,
                         f(24), f(10), w-f(48), f(32), f(25),
                         f(24), f(44), w-f(48), f(34), f(27),
                         f(24), f(85), w-f(48), f(10),
                         f(24), f(108), w-f(48), f(36), f(20))
        Screen.__init__(self, session)
        self['mode'] = Label('')
        self['position'] = Label('')
        self['progress'] = ProgressBar()
        self['hint'] = Label('')

    def update(self, mode, target, length, actual, selecting):
        self['mode'].setText(mode)
        self['position'].setText('Cel: %s / %s   |   Odtwarzanie: %s' %
                                 (timecode(target), timecode(length), timecode(actual)))
        self['progress'].setValue(min(100, max(0, int(100 * target / length)))
                                  if target is not None and length else 0)
        self['hint'].setText('OK / PLAY: odtwarzaj od tego miejsca  |  << / >>: zmień tempo' if selecting
                             else 'Lewo / prawo: -10 / +10 s  |  << / >>: wybierz pozycję')

PTS = 90000
_LOADED_KEYMAPS = set()


class StreamSeekMixin:
    def mk_init_seek_controls(self, keymap_path, context):
        from Components.ActionMap import ActionMap
        import keymapparser
        filename = str(keymap_path)
        if filename not in _LOADED_KEYMAPS:
            keymapparser.readKeymap(filename)
            _LOADED_KEYMAPS.add(filename)
        self._mk_seek_dialog = None
        self._mk_seek_visible_until = 0
        self._mk_scrub_speed = 0
        self._mk_scrub_target = None
        self._mk_scrub_length = None
        self._mk_seek_display_target = None
        self._mk_seek_display_length = None
        self._mk_seek_display_mode = ''
        self._mk_seek_timer = eTimer()
        self._mk_seek_timer.callback.append(self.mk_seek_refresh)
        self.onClose.append(self.mk_seek_cleanup)
        self._mk_seek_target = None
        self._mk_seek_observed = None
        self._mk_seek_at = float('-inf')
        self._mk_seek_notice_at = float('-inf')
        self['mkSeekActions'] = ActionMap([context], {
            'consume': self.mk_seek_consume,
            'left': self.mk_seek_back,
            'right': self.mk_seek_forward,
            'seekBack': lambda: self.mk_scrub(-1),
            'seekFwd': lambda: self.mk_scrub(1),
            'seekBackManual': lambda: self.mk_scrub(-1),
            'seekFwdManual': lambda: self.mk_scrub(1),
            'SeekbarBack': lambda: self.mk_scrub(-1),
            'SeekbarFwd': lambda: self.mk_scrub(1),
            'play': self.mk_seek_play,
            'pause': self.mk_seek_pause,
        }, -15)

    def mk_seek_consume(self):
        return 1

    def mk_seek_back(self):
        self.mk_scrub_finish(play=False)
        return self.mk_jump(-10)

    def mk_seek_forward(self):
        self.mk_scrub_finish(play=False)
        return self.mk_jump(10)

    def mk_seek_back_long(self):
        return self.mk_jump(-60)

    def mk_seek_forward_long(self):
        return self.mk_jump(60)

    @staticmethod
    def _mk_valid_pts(result):
        if (isinstance(result, (tuple, list)) and len(result) >= 2 and
                result[0] == 0 and type(result[1]) is int and result[1] >= 0):
            return result[1]
        return None

    def _mk_seek_notice(self, text):
        now = time.monotonic()
        if now - self._mk_seek_notice_at < 8:
            return
        self._mk_seek_notice_at = now
        from Screens.MessageBox import MessageBox
        self.session.open(MessageBox, text, type=MessageBox.TYPE_INFO, timeout=5)

    def mk_jump(self, seconds):
        # Always consume mapped keys: returning 0 would fall back to the native
        # OpenPLi x2/x4 winding code which ServiceApp can reject.
        self._mk_seek_success = False
        if getattr(self, 'mk_leaving', False):
            return 1
        try:
            service = self.session.nav.getCurrentService()
            seek = service.seek() if service else None
            if seek is None or not (seek.isCurrentlySeekable() & 1):
                self._mk_seek_notice('To źródło lub odtwarzacz nie udostępnia przewijania. Spróbuj innego źródła lub odtwarzacza w MENU wtyczki.')
                return 1
            now = time.monotonic()
            try:
                position = self._mk_valid_pts(seek.getPlayPosition())
            except (AttributeError, TypeError, RuntimeError):
                position = None
            target = None
            length = None
            delta = int(seconds * PTS)
            if position is not None:
                base = position
                # Native players acknowledge a seek before their position query
                # catches up. Consecutive key presses must accumulate, not all
                # seek to the same +10s point. Discard the pending point after 3s.
                if (self._mk_seek_target is not None and self._mk_seek_observed is not None and
                        now - self._mk_seek_at < 3 and
                        abs(position - self._mk_seek_observed) <= 2 * PTS and
                        abs(position - self._mk_seek_target) > 2 * PTS):
                    base = self._mk_seek_target
                target = max(0, base + delta)
                try:
                    length = self._mk_valid_pts(seek.getLength())
                except (AttributeError, TypeError, RuntimeError):
                    length = None
                if length is not None and length > 0:
                    # ServiceApp stops playback for targets beyond the duration.
                    target = min(target, max(0, length - PTS))
                delta = target - position
                if delta == 0:
                    self._mk_seek_success = True
                    self.mk_seek_display('Wybrana pozycja', target, length)
                    return 1
                result = seek.seekTo(target)
                if result != 0:
                    result = seek.seekRelative(1 if delta > 0 else -1, abs(delta))
            else:
                result = seek.seekRelative(1 if delta > 0 else -1, abs(delta))
            if result != 0:
                self._mk_seek_target = None
                self._mk_seek_notice('Odtwarzacz odrzucił zmianę pozycji. To źródło może nie obsługiwać przewijania.')
                return 1
            self._mk_seek_success = True
            self._mk_seek_target = target
            self._mk_seek_observed = position
            self._mk_seek_at = now
            # User navigation wins over an automatic resume still being retried.
            self.mk_resume = 0
            self.mk_seek_sent = False
            if getattr(self, 'seekstate', None) == self.SEEK_STATE_PAUSE:
                pause = service.pause()
                if pause is not None:
                    pause.pause()
            show = getattr(self, 'showAfterSeek', None) or getattr(self, 'show', None)
            if show:
                show()
            self.mk_seek_display('Skok %+d s' % int(seconds), target, length)
        except (AttributeError, TypeError, RuntimeError, OverflowError, ValueError):
            self._mk_seek_target = None
            self._mk_seek_notice('Nie udało się zmienić pozycji filmu. Zaczekaj na rozpoczęcie odtwarzania lub wybierz inne źródło.')
        return 1

    def mk_seek_display(self, mode, target, length):
        self._mk_seek_display_mode = mode
        self._mk_seek_display_target = target
        self._mk_seek_display_length = length
        self._mk_seek_visible_until = time.monotonic() + 5
        if self._mk_seek_dialog is None:
            self._mk_seek_dialog = self.session.instantiateDialog(SeekStatus)
        self.mk_seek_refresh()
        self._mk_seek_timer.start(250, False)

    def mk_seek_refresh(self):
        if getattr(self, 'mk_leaving', False):
            self.mk_seek_hide()
            return
        if not self._mk_scrub_speed and time.monotonic() >= self._mk_seek_visible_until:
            self.mk_seek_hide()
            return
        if self._mk_scrub_speed:
            self.mk_scrub_advance()
            self._mk_seek_display_target = int(self._mk_scrub_target)
            self._mk_seek_display_length = self._mk_scrub_length
            self._mk_seek_display_mode = 'Wybór pozycji %s x%d (skokowo)' % (
                '>>' if self._mk_scrub_speed > 0 else '<<', abs(self._mk_scrub_speed))
        actual = None
        try:
            service = self.session.nav.getCurrentService()
            seek = service.seek() if service else None
            if seek:
                actual = self._mk_valid_pts(seek.getPlayPosition())
        except (AttributeError, TypeError, RuntimeError):
            pass
        if self._mk_seek_dialog is not None:
            self._mk_seek_dialog.update(self._mk_seek_display_mode, self._mk_seek_display_target,
                                        self._mk_seek_display_length, actual, bool(self._mk_scrub_speed))
            self._mk_seek_dialog.show()

    def mk_seek_hide(self):
        self._mk_seek_timer.stop()
        if self._mk_seek_dialog is not None:
            self._mk_seek_dialog.hide()

    def mk_seek_cleanup(self):
        self._mk_scrub_speed = 0
        self.mk_seek_hide()
        if self.mk_seek_refresh in self._mk_seek_timer.callback:
            self._mk_seek_timer.callback.remove(self.mk_seek_refresh)
        if self._mk_seek_dialog is not None:
            self.session.deleteDialog(self._mk_seek_dialog)
            self._mk_seek_dialog = None

    def mk_scrub_advance(self):
        now = time.monotonic()
        self._mk_scrub_target = max(0, self._mk_scrub_target +
                                   (now - self._mk_scrub_last) * self._mk_scrub_speed * PTS)
        if self._mk_scrub_length:
            self._mk_scrub_target = min(self._mk_scrub_target, max(0, self._mk_scrub_length - PTS))
        self._mk_scrub_last = now

    def mk_scrub(self, direction):
        if getattr(self, 'mk_leaving', False):
            return 1
        try:
            if not self._mk_scrub_speed:
                service = self.session.nav.getCurrentService()
                seek = service.seek() if service else None
                if seek is None or not (seek.isCurrentlySeekable() & 1):
                    self._mk_seek_notice('To źródło nie udostępnia przewijania.')
                    return 1
                position = self._mk_valid_pts(seek.getPlayPosition())
                if position is None:
                    self._mk_seek_notice('Zaczekaj na rozpoczęcie filmu i odczyt czasu odtwarzania.')
                    return 1
                self._mk_scrub_target = position
                self._mk_scrub_length = self._mk_valid_pts(seek.getLength())
                self._mk_scrub_was_paused = self.seekstate == self.SEEK_STATE_PAUSE
                self.mk_resume = 0
                self.mk_seek_sent = False
                self.pauseService()
                self._mk_scrub_speed = 2 * direction
            else:
                self.mk_scrub_advance()
                self._mk_scrub_speed = direction * (min(64, abs(self._mk_scrub_speed)*2)
                    if self._mk_scrub_speed * direction > 0 else 2)
            self._mk_scrub_last = time.monotonic()
            self.mk_seek_display('', int(self._mk_scrub_target), self._mk_scrub_length)
        except (AttributeError, TypeError, RuntimeError, ValueError, OverflowError):
            self._mk_scrub_speed = 0
            self._mk_seek_notice('Nie udało się uruchomić przewijania. Spróbuj po rozpoczęciu filmu.')
        return 1

    def mk_scrub_finish(self, play=True):
        if not self._mk_scrub_speed:
            return False
        self.mk_scrub_advance()
        target = int(self._mk_scrub_target)
        self._mk_scrub_speed = 0
        # Use the same validated absolute seek path and boundary protection.
        try:
            service = self.session.nav.getCurrentService()
            seek = service.seek() if service else None
            position = self._mk_valid_pts(seek.getPlayPosition()) if seek else None
            self._mk_seek_target = None
            self._mk_seek_success = False
            if position is not None:
                self.mk_jump((target - position) / PTS)
            else:
                self._mk_seek_notice('Nie udało się odczytać pozycji filmu. Spróbuj ponownie.')
            if play or not self._mk_scrub_was_paused:
                self.unPauseService()
            mode = ('Odtwarzanie' if play else 'Wybrana pozycja') if self._mk_seek_success else 'Nie ustawiono pozycji'
            self.mk_seek_display(mode, target, self._mk_scrub_length)
        except (AttributeError, TypeError, RuntimeError, ValueError, OverflowError):
            self._mk_seek_notice('Nie udało się ustawić pozycji filmu. Spróbuj ponownie.')
        return True

    def mk_seek_play(self):
        if not self.mk_scrub_finish():
            self.unPauseService()
        return 1

    def mk_seek_pause(self):
        self.mk_scrub_finish(play=False)
        self.pauseService()
        return 1
