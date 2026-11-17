"""Start/reuse the existing camera skill without blocking voice startup."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeai_config import VOICE_PYTHON, CAMERA_SCRIPT
import subprocess
import threading

ROOT = Path(__file__).resolve().parents[1]


def start_camera():
    def worker():
        log_path = ROOT / 'voice/camera.log'
        try:
            with log_path.open('a') as log:
                subprocess.Popen([str(VOICE_PYTHON), '-B', '-u',
                                  str(ROOT / 'voice/vision_daemon.py'), '0'],
                                 stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                                 start_new_session=True)
            import time
            time.sleep(2)
            result = subprocess.run(
                [str(VOICE_PYTHON), '-B',
                 str(CAMERA_SCRIPT), 'status'],
                capture_output=True, text=True, timeout=45)
            with log_path.open('a', encoding='utf-8') as log:
                log.write(result.stdout + result.stderr)
            response = json.loads(result.stdout) if result.returncode == 0 else {}
            if response.get('status') == 'success' and response.get('running'):
                print('Camera service ready.', flush=True)
            else:
                print(f'Camera startup failed; see {log_path}', flush=True)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            print(f'Camera startup failed: {error}', flush=True)
    threading.Thread(target=worker, daemon=True).start()
