"""Single-hand pinch hold and relative vertical music volume adjustment."""
import time


class VolumeGesture:
    def __init__(self, change, clock=time.monotonic):
        self.change = change
        self.clock = clock
        self.reset()

    def reset(self):
        self.anchor = None
        self.since = None
        self.previous = None
        self.samples = 0

    def update(self, y, enabled):
        tick = self.clock()
        if not enabled or y is None:
            self.reset()
            return None
        if self.previous is not None and tick - self.previous > 2:
            self.reset()
        self.previous = tick
        if self.since is None:
            self.since = tick
            self.samples = 1
            return None
        self.samples += 1
        if self.anchor is None:
            if self.samples >= 2 and tick - self.since >= .6:
                self.anchor = y  # No volume jump on initial hand raise.
            return None
        delta = self.anchor - y
        if abs(delta) < .06:
            return None
        # One 5% step per sample, even after a large movement.
        value = self.change(5 if delta > 0 else -5)
        if value is not None:
            self.anchor = y
        return value
