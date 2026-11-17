"""Pause ASR from actual private mpv playback, not a particular launcher's flags."""
import time
import music

class MusicGate:
    def __init__(self,clock=time.monotonic):
        self.clock=clock;self.checked=None;self.value=False
    def blocked(self,force=False):
        now=self.clock()
        if force or self.checked is None or now-self.checked>=.3:
            reply=music.request(['get_property','pause'])
            # Neris music mpv exits at EOF. Paused tracks allow speech recognition.
            self.value=music.active() if reply is None else reply.get('data') is False
            self.checked=now
        return self.value
