"""Private persistent saved music list; edits never change playback."""
import fcntl
import json
import os
from pathlib import Path
import tempfile

STATE = Path(__file__).with_name('playlist.json')


def tracks():
    try:
        rows = json.loads(STATE.read_text())
        if not isinstance(rows, list) or not all(isinstance(row, str) for row in rows):
            raise ValueError('Invalid playlist')
        return list(dict.fromkeys(rows))
    except FileNotFoundError:
        return []


def change(filename, add=True):
    path = Path(filename).expanduser().resolve()
    if add and (not path.is_file() or path.suffix.lower() not in
                ('.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus', '.aac')):
        raise ValueError('Not a local audio file')
    STATE.parent.mkdir(parents=True, exist_ok=True)
    with STATE.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows = tracks()
        present = str(path) in rows
        if add and not present:
            rows.append(str(path))
        elif not add and present:
            rows.remove(str(path))
        else:
            return 'exists' if add else 'absent'
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=STATE.parent, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(rows, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(STATE)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
        return 'added' if add else 'removed'
