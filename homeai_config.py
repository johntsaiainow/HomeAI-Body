"""Shared runtime paths. Overrides are read from the process environment."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def path(name, default):
    return Path(os.environ.get(name, str(default))).expanduser()

COMFY_DIR = path('HOMEAI_COMFY_DIR', Path.home() / 'ComfyUI')
VOICE_DIR = path('HOMEAI_VOICE_DIR', ROOT / 'voice/.venv')
VOICE_PYTHON = path('HOMEAI_VOICE_PYTHON', VOICE_DIR / 'bin/python')
VOICE_MODELS = path('HOMEAI_VOICE_MODELS', ROOT / 'models/voice')
MUSIC_DIR = path('HOMEAI_MUSIC_DIR', Path.home() / 'Music')
CAMERA_SCRIPT = path('HOMEAI_CAMERA_SCRIPT', Path.home() / '.agents/skills/camera-vision/vision.py')
YOLO_MODEL = path('HOMEAI_YOLO_MODEL', ROOT / 'models/yolov8n.pt')
FACE_NAME = os.environ.get('HOMEAI_FACE_NAME', '使用者')
