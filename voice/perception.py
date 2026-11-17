"""Local observation events. Class-level presence, not physical-object identity."""
from datetime import datetime
import base64
import io
import json
import os
from pathlib import Path
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'voice'))
from body_bridge import dialogue, send


def now():
    return datetime.now().astimezone().isoformat()


def request(action):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(15)
        client.connect('/tmp/yolo-vision.0.sock')
        client.sendall((json.dumps({'action': action}) + '\n').encode())
        with client.makefile('rb') as stream:
            result = json.loads(stream.readline(12_000_000))
    if result.get('status') != 'success':
        raise ValueError(result.get('message', 'Camera unavailable'))
    return result


_last_object_notice = {}


def record(event):
    if event['type'] in ('gesture', 'music_control', 'preview_control',
                         'microphone_control', 'voice_output_control'):
        send({'type': 'activity', 'source': 'confirmed_gesture'})
    object_event = event['type'] in ('appeared', 'disappeared')
    show_in_chat = True
    if object_event:
        name = event['class_name']
        tick = time.monotonic()
        show_in_chat = tick - _last_object_notice.get(name, -1000) >= 60
        if show_in_chat:
            _last_object_notice[name] = tick
        event['chat_notified'] = show_in_chat
    directory = ROOT / 'logs/observations'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    event['time'] = now()
    path = directory / (event['time'][:10] + '.jsonl')
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, 'a', encoding='utf-8') as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    if event['type'] == 'voice_output_control':
        text = f"[Observation] Voice output: {event['action']}."
    elif event['type'] == 'microphone_control':
        text = f"[Observation] Microphone capture: {event['action']}."
    elif event['type'] == 'preview_control':
        text = '[Observation] Gesture requested camera preview toggle.'
    elif event['type'] == 'music_control':
        text = f"[Observation] Gesture music control requested: {event['action']}."
    elif event['type'] == 'gesture':
        text = f"[Observation] Visible hand gesture: {event['action']} (identity unverified)."
    elif event['type'] == 'expression':
        text = f"[Observation] Visible face: {event['action']} (not an emotion or identity judgment)."
    elif event['type'] == 'appeared':
        text = f"[Observation] Object class appeared: {event['class_name']}; first seen {event['first_seen']}."
    else:
        text = (f"[Observation] Object class no longer detected: {event['class_name']}; "
                f"last seen {event['last_seen']}; confirmed absent {event['time']}. "
                'May be occluded or missed by the detector.')
    if show_in_chat:
        dialogue('assistant', text)
    print(text + ('' if show_in_chat else ' [chat notification suppressed]'), flush=True)


class Presence:
    def __init__(self, emit=record, clock=time.monotonic, appear_seconds=2, disappear_seconds=10):
        self.states = {}
        self.emit = emit
        self.clock = clock
        self.appear_seconds = appear_seconds
        self.disappear_seconds = disappear_seconds
        self.previous_sample = None

    def update(self, names, stamp):
        tick = self.clock()
        # Do not infer continuous absence/presence across camera outages or stalls.
        if self.previous_sample is not None and tick - self.previous_sample > 3:
            for state in self.states.values():
                state['hits'] = 0
                state['misses'] = 0
                state.pop('missing_since', None)
        self.previous_sample = tick
        for name in set(names) | set(self.states):
            state = self.states.setdefault(name, {'present': False, 'hits': 0, 'misses': 0})
            if name in names:
                if state['hits'] == 0 and not state['present']:
                    state['first_seen'] = stamp
                    state['visible_since'] = tick
                state['hits'] += 1
                state['misses'] = 0
                state.pop('missing_since', None)
                state['last_seen'] = stamp
                if (not state['present'] and state['hits'] >= 3
                        and tick - state['visible_since'] >= self.appear_seconds):
                    state['present'] = True
                    self.emit({'type': 'appeared', 'class_name': name,
                               'first_seen': state['first_seen'], 'last_seen': stamp})
            else:
                state['hits'] = 0
                state['misses'] += 1
                state.setdefault('missing_since', tick)
                if (state['present'] and state['misses'] >= 3
                        and tick - state['missing_since'] >= self.disappear_seconds):
                    state['present'] = False
                    self.emit({'type': 'disappeared', 'class_name': name,
                               'first_seen': state['first_seen'], 'last_seen': state['last_seen']})


class Expressions:
    def __init__(self):
        self.detector = None
        self.streaks = {}
        self.last = {}
        self.retry_at = 0

    def initialize(self):
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        import zipfile
        path = ROOT / 'models/expression/face_landmarker.task'
        partial = path.with_suffix('.task.part')
        if not path.exists() and partial.exists() and zipfile.is_zipfile(partial):
            # Validate the complete ZIP payload before publishing.
            with zipfile.ZipFile(partial) as archive:
                if archive.testzip() is not None:
                    raise ValueError('Incomplete expression model')
            partial.rename(path)
        options = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(path)),
            num_faces=1, output_face_blendshapes=True)
        self.detector = vision.FaceLandmarker.create_from_options(options)
        self.mp = mp
        print('Expression detector ready', flush=True)

    def update(self):
        if self.detector is None:
            if time.monotonic() < self.retry_at:
                return
            self.retry_at = time.monotonic() + 60
            try:
                self.initialize()
            except Exception as error:
                print(f'Expression detector not ready: {error}', flush=True)
                return
        import numpy as np
        from PIL import Image
        response = request('capture')
        pixels = np.asarray(Image.open(io.BytesIO(base64.b64decode(response['frame']))).convert('RGB'))
        result = self.detector.detect(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=pixels))
        scores = {c.category_name: c.score for c in result.face_blendshapes[0]} if result.face_blendshapes else {}
        actions = {
            'Smile': min(scores.get('mouthSmileLeft', 0), scores.get('mouthSmileRight', 0)) >= 0.5,
            'Eyes closed': min(scores.get('eyeBlinkLeft', 0), scores.get('eyeBlinkRight', 0)) >= 0.5,
            'Mouth open': scores.get('jawOpen', 0) >= 0.5,
        }
        for action, active in actions.items():
            self.streaks[action] = self.streaks.get(action, 0) + 1 if active else 0
            if self.streaks[action] == 3 and time.monotonic() - self.last.get(action, -100) >= 30:
                record({'type': 'expression', 'action': action, 'identity': 'unverified'})
                self.last[action] = time.monotonic()


class Gestures:
    RULES = {'OK', 'Pinch', 'Number_1', 'Number_2', 'Number_3', 'Number_4', 'Number_5', 'Vulcan_Salute'}
    ALLOWED = {'Open_Palm', 'Closed_Fist', 'Thumb_Up', 'Thumb_Down',
               'Victory', 'Pointing_Up', 'ILoveYou'}

    def __init__(self):
        self.detector = None
        self.retry_at = 0
        self.streaks = {}
        self.last = {}
        from gesture_music import Controller
        self.music_control = Controller()
        from preview_gesture import toggle
        self.preview_control = Controller(execute=toggle, mapping={'ILoveYou': 'toggle_preview'})
        import microphone
        self.microphone_control = Controller(execute=microphone.toggle, mapping={'Thumb_Down': 'toggle_microphone'})
        import voice_output
        self.voice_output_control = Controller(execute=voice_output.toggle, mapping={'OK': 'toggle_voice_output'})
        from vulcan_greeting import greet
        self.vulcan_control = Controller(execute=greet, mapping={'Vulcan_Salute': 'greet'})
        from volume_gesture import VolumeGesture
        import music
        self.volume_control = VolumeGesture(music.adjust_volume)

    def initialize(self):
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        import zipfile
        path = ROOT / 'models/gesture/gesture_recognizer.task'
        partial = path.with_suffix('.task.part')
        if not path.exists() and partial.exists() and zipfile.is_zipfile(partial):
            with zipfile.ZipFile(partial) as archive:
                if archive.testzip() is not None:
                    raise ValueError('Incomplete gesture model')
            partial.rename(path)
        self.detector = vision.GestureRecognizer.create_from_options(
            vision.GestureRecognizerOptions(
                base_options=python.BaseOptions(model_asset_path=str(path)), num_hands=2,
                min_hand_detection_confidence=0.35,
                min_hand_presence_confidence=0.35))
        self.mp = mp
        print('Gesture detector ready', flush=True)

    def update(self):
        if self.detector is None:
            if time.monotonic() < self.retry_at:
                return
            self.retry_at = time.monotonic() + 60
            try:
                self.initialize()
            except Exception as error:
                print(f'Gesture detector not ready: {error}', flush=True)
                return
        import numpy as np
        from PIL import Image
        response = request('capture')
        pixels = np.asarray(Image.open(io.BytesIO(base64.b64decode(response['frame']))).convert('RGB'))
        result = self.detector.recognize(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=pixels))
        from hand_rules import classify
        rules = set()
        pinch_y = None
        vulcan_hands = set()
        for hand_index, hand in enumerate(result.hand_landmarks):
            hand_rules = classify(hand, pixels.shape[1], pixels.shape[0])
            rules.update(hand_rules)
            if 'Vulcan_Salute' in hand_rules:
                vulcan_hands.add(hand_index)
            if len(result.hand_landmarks) == 1 and 'Pinch' in hand_rules:
                pinch_y = (hand[4].y + hand[8].y) / 2
        diagnostic = {
            'time': now(), 'hands': len(result.hand_landmarks),
            'rule_candidates': sorted(rules),
            'candidates': [{'name': items[0].category_name, 'score': round(items[0].score, 3)}
                           for items in result.gestures if items],
        }
        temporary = ROOT / 'body/gesture-status.tmp'
        temporary.write_text(json.dumps(diagnostic))
        temporary.replace(ROOT / 'body/gesture-status.json')
        if getattr(self, 'previous_hands', None) != diagnostic['hands']:
            print(f"Hand detection: {diagnostic['hands']} hand(s), {diagnostic['candidates']}", flush=True)
            self.previous_hands = diagnostic['hands']
        visible = {items[0].category_name for hand_index, items in enumerate(result.gestures)
                   if hand_index not in vulcan_hands and items and items[0].score >= ({'Closed_Fist': 0.5, 'Thumb_Up': 0.55}.get(items[0].category_name, 0.7))
                   and items[0].category_name in self.ALLOWED}
        # Avoid logging equivalent labels twice for the same pose.
        for rule, builtin in [('Number_1', 'Pointing_Up'), ('Number_2', 'Victory'),
                              ('Number_5', 'Open_Palm')]:
            if rule in rules:
                visible.discard(builtin)
        visible.update(rules)
        from gesture_music import enabled
        control_enabled = enabled()
        self.vulcan_control.update(visible, control_enabled)
        if self.voice_output_control.update(visible, control_enabled):
            import voice_output
            record({'type': 'voice_output_control', 'action': 'On' if voice_output.enabled() else 'Off', 'identity': 'unverified'})
        if self.microphone_control.update(visible, control_enabled):
            import microphone
            record({'type': 'microphone_control', 'action': 'Off' if microphone.muted() else 'On', 'identity': 'unverified'})
        if self.preview_control.update(visible, control_enabled):
            record({'type': 'preview_control', 'action': 'toggle', 'identity': 'unverified'})
        value = self.volume_control.update(pinch_y, control_enabled)
        if value is not None:
            record({'type': 'music_control', 'action': f'volume {value:.0f}%', 'identity': 'unverified'})
        # Pinch is exclusive: do not interpret the same hand as Stop/Pause.
        control_action = self.music_control.update(set() if 'Pinch' in rules else visible,
                                                  control_enabled)
        if control_action:
            record({'type': 'music_control', 'action': control_action, 'identity': 'unverified'})
        for action in self.ALLOWED | self.RULES:
            self.streaks[action] = self.streaks.get(action, 0) + 1 if action in visible else 0
            if self.streaks[action] == 3 and time.monotonic() - self.last.get(action, -100) >= 30:
                record({'type': 'gesture', 'action': action, 'identity': 'unverified',
                        'method': 'landmark_rule' if action in self.RULES else 'model'})
                self.last[action] = time.monotonic()


def main():
    presence, expressions, gestures = Presence(), Expressions(), Gestures()
    print('Observation recording active; objects: confidence >=0.55, appear 2s, absent 10s, chat cooldown 60s.', flush=True)
    while True:
        try:
            result = request('analyze')
            names = {item['class_name'] for item in result.get('detections', [])
                     if item.get('confidence', 0) >= 0.55}
            presence.update(names, now())
            for detector in (expressions, gestures):
                try:
                    detector.update()
                except Exception as error:
                    print(f'Face/hand sample failed: {error}', flush=True)
        except Exception as error:
            # Failed camera requests never count as evidence of disappearance.
            print(f'Observation sample failed: {error}', flush=True)
        time.sleep(0.5)


if __name__ == '__main__':
    main()
