"""Send one local action command; no Qt dependency."""
import argparse
import json
from pathlib import Path
import socket


def send(action, path=None):
    path = path or Path(__file__).resolve().parent / 'control.sock'
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5)
        client.connect(str(path))
        client.sendall((json.dumps({'action': action}) + '\n').encode())
        response = bytearray()
        while b'\n' not in response:
            chunk = client.recv(4096)
            if not chunk:
                raise RuntimeError('Player closed without a response')
            response.extend(chunk)
            if len(response) > 8192:
                raise RuntimeError('Response too large')
        return json.loads(response.split(b'\n', 1)[0])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action')
    args = parser.parse_args()
    try:
        result = send(args.action)
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(0 if result.get('ok') else 1)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f'控制失敗（請確認播放器已啟動）：{error}\n')
