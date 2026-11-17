"""Request a preview toggle through the voice command queue."""
import json
import os
import socket


def toggle(action):
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(.5)
            client.connect(f'/run/user/{os.getuid()}/neris-stage2-voice.sock')
            client.sendall((json.dumps({'text':'__neris_toggle_preview__'})+'\n').encode())
            return json.loads(client.recv(4096)).get('ok') is True
    except (OSError, ValueError):
        return False
