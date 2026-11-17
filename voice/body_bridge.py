"""Best-effort body notifications; voice must work without the player."""
import json
from pathlib import Path
import socket
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'body'))
from history import save

SOCKET = Path(__file__).resolve().parents[1] / 'body/control.sock'


def status(text):
    return send({'type': 'status', 'text': text})


def notify(action):
    return send({'action': action})


def dialogue(role, text):
    saved = False
    try:
        save(role, text)
        saved = True
    except OSError as error:
        print(f'對話存檔失敗：{error}', file=sys.stderr)
    return send({'type': 'dialogue', 'role': role, 'text': text, 'persisted': saved})


def send(message):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(0.2)
            client.connect(str(SOCKET))
            client.sendall((json.dumps(message, ensure_ascii=False) + '\n').encode())
            return True
    except OSError:
        return False
