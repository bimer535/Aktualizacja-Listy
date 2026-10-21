"""Debounced, cancellable Enigma2 metadata requests and display formatting."""
from pathlib import Path
import codecs
import json
import time

from enigma import eConsoleAppContainer, eTimer


def programme_line(programme):
    if not programme:
        return "Brak danych CANAL+"
    start = time.strftime("%H:%M", time.localtime(programme["start"]))
    end = time.strftime("%H:%M", time.localtime(programme["end"]))
    return "%s–%s  %s" % (start, end, programme["title"])


def programme_details(programme):
    if not programme:
        return ""
    return "\n".join(dict.fromkeys(p for p in
        (programme.get("subtitle"), programme.get("description")) if p))


def programme_progress(programme):
    if not programme:
        return 0
    duration = programme["end"] - programme["start"]
    return max(0, min(100, int(100 * (time.time() - programme["start"]) / max(1, duration))))


class EpgLoader:
    def __init__(self, callback):
        self.callback = callback
        self.channel = self.active_channel = None
        self.container = None
        self.running = self.closed = False
        self.paused = True
        self.buffer = ""
        self.delivered = False
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.timer = eTimer()
        self.timer.callback.append(self.start)
        self.refresh_timer = eTimer()
        self.refresh_timer.callback.append(self.start)

    def request(self, channel):
        self.channel = str(channel) if channel is not None else None
        self.refresh_timer.stop()
        self.timer.stop()
        if self.channel is not None and not self.paused and not self.closed:
            self.timer.start(250, True)

    def resume(self):
        self.paused = False
        self.request(self.channel)

    def pause(self):
        self.paused = True
        self.timer.stop()
        self.refresh_timer.stop()
        container = self.container
        self.detach()
        self.container = None
        if container is not None and self.running:
            container.sendCtrlC()
        self.running = False
        self.buffer = ""

    def start(self):
        if self.running or self.paused or self.closed or self.channel is None:
            return
        self.detach()
        self.container = eConsoleAppContainer()
        self.container.dataAvail.append(self.data)
        self.container.appClosed.append(self.finished)
        self.active_channel = self.channel
        self.buffer = ""
        self.delivered = False
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.running = True
        python = "/usr/bin/python3"
        worker = str(Path(__file__).with_name("epg_worker.py"))
        if self.container.execute(python, python, "-u", worker, "--channel", self.channel):
            self.finished(1)

    def data(self, body):
        if self.closed or self.paused:
            return
        body = self.decoder.decode(body) if isinstance(body, bytes) else body
        self.buffer = (self.buffer + body)[-65536:]
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            try:
                event = json.loads(line)
            except (TypeError, ValueError):
                continue
            if (isinstance(event, dict) and event.get("channel_id") == self.channel
                    and event.get("stage") in ("epg_loaded", "epg_error")):
                self.delivered = True
                self.callback(event)

    def finished(self, code):
        self.running = False
        if self.closed or self.paused:
            return
        if self.channel != self.active_channel:
            self.timer.start(100, True)
        else:
            if not self.delivered:
                self.callback({"stage": "epg_error", "channel_id": self.channel,
                               "reason": "epg_unavailable"})
            self.refresh_timer.start(30000, True)

    def detach(self):
        if self.container is not None:
            for signal, callback in ((self.container.dataAvail, self.data),
                                     (self.container.appClosed, self.finished)):
                if callback in signal:
                    signal.remove(callback)

    def close(self):
        self.closed = True
        self.pause()
