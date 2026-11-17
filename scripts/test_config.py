"""Check path overrides from a clean working directory without optional dependencies."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ConfigTests(unittest.TestCase):
    def query(self, code, overrides=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith('HOMEAI_')}
        env.update(overrides or {})
        with tempfile.TemporaryDirectory() as directory:
            return subprocess.check_output(
                [sys.executable, '-B', '-c',
                 f'import sys; sys.path.insert(0, {str(ROOT)!r}); ' + code],
                cwd=directory, env=env, text=True).strip()

    def test_default_voice_is_checkout_local(self):
        self.assertEqual(self.query('from homeai_config import VOICE_PYTHON; print(VOICE_PYTHON)'),
                         str(ROOT / 'voice/.venv/bin/python'))

    def test_override_expands_home_and_preserves_spaces(self):
        self.assertEqual(self.query('from homeai_config import COMFY_DIR; print(COMFY_DIR)',
                                    {'HOMEAI_COMFY_DIR': '~/My ComfyUI'}),
                         str(Path.home() / 'My ComfyUI'))

    def test_voice_directory_sets_default_interpreter(self):
        self.assertEqual(self.query('from homeai_config import VOICE_PYTHON; print(VOICE_PYTHON)',
                                    {'HOMEAI_VOICE_DIR': '/tmp/custom voice'}),
                         '/tmp/custom voice/bin/python')

if __name__ == '__main__':
    unittest.main()
