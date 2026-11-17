"""Stage-two process manager. Never stops shared camera or stage one."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def display_status(text):
    # Desktop launchers have no terminal; report startup readiness in the body UI.
    import socket
    import json
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(1)
            client.connect(str(ROOT / 'body/control.sock'))
            client.sendall((json.dumps({'type': 'status', 'text': text}) + '\n').encode())
            client.recv(4096)
    except OSError:
        pass


def processes():
    found = {'body': [], 'voice': [], 'preview': [], 'perception': [], 'asr_worker': [], 'taigi_tts': []}
    names = {'body/player.py': 'body', 'voice/agent.py': 'voice', 'body/preview.py': 'preview', 'voice/perception.py': 'perception', 'asr/worker.py': 'asr_worker', 'tts-taigi/worker.py': 'taigi_tts'}
    for item in Path('/proc').iterdir():
        if not item.name.isdigit():
            continue
        try:
            if item.stat().st_uid != os.getuid():
                continue
            args = (item / 'cmdline').read_bytes().split(b'\0')
            for script, key in names.items():
                if str(ROOT / script).encode() in args:
                    found[key].append(int(item.name))
        except (OSError, ProcessLookupError):
            pass
    return found


def start():
    found = processes()
    env = os.environ.copy()
    env.update(XDG_RUNTIME_DIR=f'/run/user/{os.getuid()}',
               DBUS_SESSION_BUS_ADDRESS=f'unix:path=/run/user/{os.getuid()}/bus',
               WAYLAND_DISPLAY='wayland-0', QT_QPA_PLATFORM='wayland', PYTHONUNBUFFERED='1')
    for key, script, log in [('body', 'body/start.sh', 'body/player.log'),
                             ('voice', 'voice/start.sh', 'voice/agent.log')]:
        if key == 'voice':
            from llm_service import ensure
            display_status('Checking local LLM server; cold model loading may take a moment…')
            result = ensure()
            print('LLM: ' + result['message'], flush=True)
            display_status(result['message'])
        if found[key]:
            print(f'{key}: already running')
            continue
        if key == 'body':
            (ROOT / 'body/control.sock').unlink(missing_ok=True)
        with (ROOT / log).open('a') as output:
            subprocess.Popen(['bash', str(ROOT / script)], env=env,
                             stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                             start_new_session=True)
        time.sleep(1)
        print(f'{key}: start requested')
    if not found['perception']:
        with (ROOT / 'voice/perception.log').open('a') as output:
            subprocess.Popen([str(ROOT / 'body/.venv/bin/python'), '-B', '-u',
                              str(ROOT / 'voice/perception.py')], env=env,
                             stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                             start_new_session=True)
        print('perception: start requested')


def stop():
    sys.path.insert(0, str(ROOT / 'body'))
    import music
    music.stop()
    found = processes()
    for key in ('perception', 'voice', 'asr_worker', 'taigi_tts', 'preview', 'body'):
        for pid in found[key]:
            try:
                os.kill(pid, 15)
            except ProcessLookupError:
                pass
    from llm_service import stop_owned
    print('LLM: ' + stop_owned())
    print('Stage-two stop requested; shared camera service and stage one are untouched.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'stop', 'status'])
    args = parser.parse_args()
    import fcntl
    with (ROOT / '.system.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == 'start':
            start()
        elif args.action == 'stop':
            stop()
        else:
            for key, pids in processes().items():
                print(f'{key}: {pids or "stopped"}')
