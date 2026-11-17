"""Control only Neris stage-two music via a private mpv IPC socket."""
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time

IPC = Path(f'/run/user/{os.getuid()}/neris-stage2-music.sock')
LAST = Path(__file__).with_name('music-state.json')
_remembered = None


def remember(filename):
    global _remembered
    try:
        path = Path(filename).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() not in ('.mp3','.flac','.wav','.m4a','.ogg','.opus','.aac'):
            return
        if _remembered == str(path):
            return
        with tempfile.NamedTemporaryFile(mode='w',dir=LAST.parent,delete=False) as stream:
            json.dump({'last_path': str(path)},stream,ensure_ascii=False)
            temporary = Path(stream.name)
        try:
            temporary.replace(LAST)
        finally:
            temporary.unlink(missing_ok=True)
        _remembered = str(path)
    except (OSError, TypeError, ValueError):
        pass


def last_track():
    try:
        path = Path(json.loads(LAST.read_text())['last_path'])
        return str(path) if path.is_file() else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def loaded_track():
    reply = request(['get_property', 'path'])
    value = reply.get('data') if reply else None
    return value if isinstance(value, str) and value else None


def repeat_one():
    reply = request(['get_property', 'loop-file'])
    if reply is None:return None
    return reply.get('data') not in (None, False, 0, 'no', '0')


def toggle_repeat_one():
    if not loaded_track():return None
    before = repeat_one()
    if before is None:return None
    desired = not before
    if request(['set_property', 'loop-file', 'inf' if desired else 'no']) is None:return None
    return desired if repeat_one() is desired else None


def replay(require_loaded=False):
    current = request(['get_property', 'path'])
    current_path = current.get('data') if current else None
    filename = current_path or (None if require_loaded else last_track())
    if not isinstance(filename, str) or not Path(filename).is_file():
        return {'ok': False, 'reason': 'no_track'}
    remember(filename)
    if current_path:
        if request(['seek', 0, 'absolute+exact']) is None or request(['set_property', 'pause', False]) is None:
            return {'ok': False, 'reason': 'player_rejected'}
    else:
        try:play(filename)
        except OSError:return {'ok': False, 'reason': 'launch_failed'}
    for _ in range(20):
        path = request(['get_property', 'path'])
        position = request(['get_property', 'time-pos'])
        pause = request(['get_property', 'pause'])
        seconds = position.get('data') if position else None
        if (path and path.get('data') == filename and isinstance(seconds, (int,float))
                and 0 <= seconds < 3 and pause and pause.get('data') is False):
            return {'ok': True, 'path': filename}
        time.sleep(.1)
    return {'ok': False, 'reason': 'unconfirmed'}


def active():
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(0.2)
            client.connect(str(IPC))
        return True
    except OSError:
        return False


def request(args):
    """Return an acknowledged mpv reply, ignoring unrelated events."""
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(0.3)
            client.connect(str(IPC))
            client.sendall((json.dumps({'command': args, 'request_id': 1}) + '\n').encode())
            with client.makefile('rb') as stream:
                for _ in range(20):
                    line = stream.readline(65536)
                    if not line:
                        break
                    reply = json.loads(line)
                    if reply.get('request_id') == 1:
                        return reply if reply.get('error') == 'success' else None
    except (OSError, ValueError):
        pass
    return None


def volume():
    reply = request(['get_property', 'volume'])
    value = reply.get('data') if reply else None
    return float(value) if isinstance(value, (int, float)) else None


def adjust_volume(delta):
    current = volume()
    if current is None:
        return None
    target = max(0, min(100, current + delta))
    if request(['set_property', 'volume', target]) is None:
        return None
    return volume()


def command(args):
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(0.3)
            client.connect(str(IPC))
            client.sendall((json.dumps({'command': args}) + '\n').encode())
        return True
    except OSError:
        return False


def stop():
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(0.3)
            client.connect(str(IPC))
            client.sendall((json.dumps({'command': ['quit']}) + '\n').encode())
        return True
    except OSError:
        return False


def play_playlist():
    """Load a snapshot into mpv's native queue; EOF advances without the UI."""
    import playlist
    try:
        saved = playlist.tracks()
    except (OSError, ValueError, TypeError):
        return {'ok': False, 'reason': 'invalid_list'}
    tracks = [str(Path(path).expanduser().resolve()) for path in saved
              if Path(path).is_file() and Path(path).suffix.lower() in
              ('.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus', '.aac')
              and '\n' not in path and '\r' not in path]
    if not tracks:
        return {'ok': False, 'reason': 'empty', 'skipped': len(saved)}
    temporary = None
    process = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m3u8', encoding='utf-8',
                                         dir=IPC.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write('#EXTM3U\n' + '\n'.join(tracks) + '\n')
        stop()
        for _ in range(20):
            if not IPC.exists():break
            time.sleep(.05)
        process = subprocess.Popen(['mpv', '--no-terminal', '--no-video',
                                    '--loop-file=no', '--loop-playlist=no',
                                    f'--input-ipc-server={IPC}', f'--playlist={temporary}'])
        for _ in range(40):
            if process.poll() is not None:break
            count = request(['get_property', 'playlist-count'])
            path = loaded_track()
            position = request(['get_property', 'time-pos'])
            if (count and count.get('data') == len(tracks) and path in tracks
                    and position and isinstance(position.get('data'), (int, float))):
                remember(path)
                return {'ok': True, 'count': len(tracks), 'path': path,
                        'skipped': len(saved)-len(tracks)}
            time.sleep(.1)
        return {'ok': False, 'reason': 'unconfirmed'}
    except OSError:
        return {'ok': False, 'reason': 'launch_failed'}
    finally:
        if temporary:temporary.unlink(missing_ok=True)


def playlist_step(direction):
    if direction not in (-1, 1):return False
    before = request(['get_property', 'playlist-pos'])
    count = request(['get_property', 'playlist-count'])
    if not before or not count:return False
    index, total = before.get('data'), count.get('data')
    if not isinstance(index, int) or not isinstance(total, int):return False
    target = index + direction
    if not 0 <= target < total:return False
    if request(['playlist-next' if direction > 0 else 'playlist-prev', 'weak']) is None:return False
    after = request(['get_property', 'playlist-pos'])
    return bool(after and after.get('data') == target)


def play(filename):
    stop()
    for _ in range(20):
        if not IPC.exists():
            break
        time.sleep(0.05)
    process = subprocess.Popen(['mpv', '--no-terminal', '--no-video',
                                f'--input-ipc-server={IPC}', str(filename)])
    remember(filename)
    return process
