"""Local text-command ingress for the stage-two command queue."""
import json
import os
from pathlib import Path
import socket

PATH = Path(f'/run/user/{os.getuid()}/neris-stage2-voice.sock')


def serve(queue):
    # The start script prevents simultaneous voice instances.
    PATH.unlink(missing_ok=True)
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(str(PATH))
        os.chmod(PATH, 0o600)
        server.listen(4)
        while True:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(1)
                try:
                    data = bytearray()
                    while b'\n' not in data:
                        chunk = connection.recv(4096)
                        if not chunk:
                            raise ValueError('Incomplete request')
                        data.extend(chunk)
                        if len(data) > 16384:
                            raise ValueError('Command too long')
                    request = json.loads(data.split(b'\n', 1)[0])
                    text = request.get('text')
                    if not isinstance(text, str) or not text.strip():
                        raise ValueError('Empty command')
                    queue.put(text.strip())
                    reply = {'ok': True}
                except (ValueError, AttributeError, OSError) as error:
                    reply = {'ok': False, 'error': str(error)}
                try:
                    connection.sendall((json.dumps(reply) + '\n').encode())
                except OSError:
                    pass
