"""Monotonic, interaction-based body sleep policy (not OS suspend)."""
import time

class IdleSleep:
    def __init__(self,timeout=300,clock=time.monotonic):
        self.timeout=timeout
        self.clock=clock
        self.last_activity=clock()
        self.sleeping=False

    def touch(self):
        was_sleeping=self.sleeping
        self.last_activity=self.clock()
        self.sleeping=False
        return was_sleeping

    def poll(self,music_playing=False,speaking=False):
        if music_playing:
            self.touch()
            return False
        if self.sleeping or speaking:return False
        if self.clock()-self.last_activity>=self.timeout:
            self.sleeping=True
            return True
        return False
