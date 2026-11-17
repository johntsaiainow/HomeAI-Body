"""Queue a bounded local Vulcan greeting; no direct audio or music control."""
import json
import os
from pathlib import Path
import socket
import time

COMMAND='__neris_vulcan_salute__'
_last_sent=None


def reply(language):
    text={'zh':'願你平安長壽。','en':'Peace and long life.',
          'nan':'祝你平安閣長壽。'}.get(language,'願你平安長壽。')
    audio=Path(__file__).resolve().parents[1]/'tts-taigi/samples/vulcan_greeting_nan.wav'
    return {'text':text,'force_english':language=='en',
            'audio_file':str(audio) if language=='nan' and audio.is_file() else None}


def greet(action=None):
    global _last_sent
    now=time.monotonic()
    if _last_sent is not None and now-_last_sent<15:return False
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(.5)
            client.connect(f'/run/user/{os.getuid()}/neris-stage2-voice.sock')
            client.sendall((json.dumps({'text':COMMAND})+'\n').encode())
            success=json.loads(client.recv(4096)).get('ok') is True
        if success:
            _last_sent=now
            print('Vulcan greeting queued',flush=True)
        return success
    except (OSError,ValueError):return False
