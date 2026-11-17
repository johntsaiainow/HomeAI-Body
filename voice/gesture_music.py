"""Opt-in music control with hold, release and stale-sample guards."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'body'))
import music

SETTINGS = ROOT / 'body/gesture-music.json'
MAPPING = {'Thumb_Up': 'resume', 'Open_Palm': 'pause', 'Number_5': 'pause',
           'Closed_Fist': 'stop', 'Number_1': 'replay', 'Pointing_Up': 'replay',
           'Number_2': 'repeat_one', 'Victory': 'repeat_one',
           'Number_3': 'playlist_add', 'Number_4': 'playlist_remove'}


class Controller:
    def __init__(self, clock=time.monotonic, execute=None, mapping=None, context=None):
        self.mapping = MAPPING if mapping is None else mapping
        self.clock = clock
        self.execute = execute or self.perform
        self.context = context or music.loaded_track
        self.reset()

    def reset(self):
        self.candidate = None
        self.since = 0
        self.previous = 0
        self.armed = True
        self.releases = 0
        self.samples = 0
        self.music_context = None

    @staticmethod
    def perform(action):
        if action in ('playlist_add', 'playlist_remove'):
            track = music.loaded_track()
            if not track:return False
            import playlist
            from body_bridge import send
            from music_feedback import enqueue
            try:
                result = playlist.change(track, add=action == 'playlist_add')
                text = {'added':'Added current song', 'removed':'Removed current song',
                        'exists':'Song already saved', 'absent':'Song not in list'}[result]
                key = 'playlist_' + result
                ok = True
            except (OSError, ValueError, TypeError):
                text, key, ok = 'Update failed', 'playlist_failed', False
            send({'type':'control_status','text':'Playlist · ' + text})
            if not enqueue(key):
                send({'type':'control_status','text':'Playlist · '+text+' · Voice unavailable'})
            return ok
        if action in ('replay', 'repeat_one'):
            if not music.loaded_track():return False
            from body_bridge import send
            from music_feedback import enqueue
            def feedback(text,key=None):
                send({'type':'control_status','text':text})
                if key and not enqueue(key):
                    send({'type':'control_status','text':text+' · Voice unavailable'})
            feedback('Replay · Executing' if action=='replay' else 'Repeat One · Executing')
            if action == 'replay':
                result = music.replay(require_loaded=True)
                ok = result.get('ok') is True
                feedback('Replay · Restarted' if ok else 'Replay · Failed', 'replay' if ok else 'replay_failed')
                return ok
            result = music.toggle_repeat_one()
            if result is None:
                feedback('Repeat One · Failed','repeat_failed')
                return False
            feedback('Repeat One · On' if result else 'Repeat One · Off','repeat_on' if result else 'repeat_off')
            return True
        if not music.active():
            if action != 'resume':
                return False
            import socket
            try:
                with socket.socket(socket.AF_UNIX) as client:
                    client.settimeout(0.5)
                    import os
                    client.connect(f'/run/user/{os.getuid()}/neris-stage2-voice.sock')
                    client.sendall((json.dumps({'text': '__neris_choose_music__'}) + '\n').encode())
                    return json.loads(client.recv(4096)).get('ok') is True
            except (OSError, ValueError):
                return False
        args = ['quit'] if action == 'stop' else ['set_property', 'pause', action == 'pause']
        return music.command(args)

    def update(self, visible, enabled):
        now = self.clock()
        if not enabled:
            self.reset()
            return None
        if self.previous and now - self.previous > 2:
            self.candidate = None
            self.samples = 0
        self.previous = now
        actions = {self.mapping[name] for name in visible if name in self.mapping}
        # Ambiguous two-hand commands must never trigger anything.
        if len(actions) != 1:
            self.candidate = None
            self.samples = 0
            if not visible:
                self.releases += 1
                if self.releases >= 2:
                    self.armed = True
            else:
                self.releases = 0
            return None
        self.releases = 0
        if not self.armed:
            return None
        action = next(iter(actions))
        if action in ('replay', 'repeat_one', 'playlist_add', 'playlist_remove'):
            current = self.context()
            if not current:
                self.candidate = None;self.samples = 0;self.music_context = None
                return None
            if current != self.music_context:
                self.candidate = None;self.samples = 0;self.music_context = current
        if self.candidate != action:
            self.candidate, self.since, self.samples = action, now, 1
            return None
        self.samples += 1
        hold = 1.5 if action == 'repeat_one' else 1.0
        if self.samples >= 2 and now - self.since >= hold:
            self.armed = False
            return action if self.execute(action) else None
        return None


def enabled():
    try:
        return json.loads(SETTINGS.read_text()).get('enabled', True) is True
    except FileNotFoundError:
        return True
    except (OSError, ValueError, AttributeError):
        return False
