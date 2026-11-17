"""Persisted software microphone capture switch for stage two only."""
import json
from pathlib import Path

SETTINGS = Path(__file__).resolve().parent / 'microphone.json'


def muted():
    try:
        return json.loads(SETTINGS.read_text()).get('muted', False) is True
    except FileNotFoundError:
        return False
    except (OSError, ValueError, AttributeError):
        return True  # Fail closed if settings become unreadable.


def set_muted(value):
    import os
    import tempfile
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w',dir=SETTINGS.parent,delete=False) as output:
            name=output.name
            json.dump({'muted':bool(value)},output)
        os.replace(name,SETTINGS)
    finally:
        if name and Path(name).exists():
            Path(name).unlink()


def toggle(action=None):
    try:
        set_muted(not muted())
        return True
    except OSError:
        return False
