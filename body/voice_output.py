"""Stage-two TTS output preference, independent of capture and music."""
import json
import os
from pathlib import Path
import tempfile

SETTINGS = Path(__file__).resolve().parent / 'voice-output.json'


def enabled():
    try:
        return json.loads(SETTINGS.read_text()).get('enabled', True) is True
    except FileNotFoundError:
        return True
    except (OSError, ValueError, AttributeError):
        return False


def toggle(action=None):
    filename = None
    try:
        value = not enabled()
        with tempfile.NamedTemporaryFile(mode='w', dir=SETTINGS.parent, delete=False) as output:
            filename = output.name
            json.dump({'enabled': value}, output)
        os.replace(filename, SETTINGS)
        return True
    except OSError:
        return False
    finally:
        if filename and Path(filename).exists():
            Path(filename).unlink()
