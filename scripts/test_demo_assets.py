"""Check demo installation cannot overwrite private media or partially copy on conflict."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import demo_assets

class DemoTests(unittest.TestCase):
    def test_install_is_repeatable_and_refuses_conflicts_before_copying(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(demo_assets, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                demo_assets.install()
                demo_assets.install()
                rows=json.loads(demo_assets.MANIFEST.read_text())['files']
                for row in rows:
                    self.assertEqual(demo_assets.digest(root/row['path']), row['sha256'])
                first=root/rows[0]['path']
                first.unlink()
                private=root/rows[-1]['path']
                private.write_bytes(b'private media must survive')
                with self.assertRaises(SystemExit):
                    demo_assets.install()
                self.assertFalse(first.exists())
                self.assertEqual(private.read_bytes(), b'private media must survive')

if __name__ == '__main__':
    unittest.main()
