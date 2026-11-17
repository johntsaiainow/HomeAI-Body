import tempfile
import unittest
from pathlib import Path
import wave
from unittest.mock import patch
import numpy as np
import beat_sync


class BeatTests(unittest.TestCase):
    def test_phase(self):
        self.assertEqual(beat_sync.phase(1,120,0,8,16),(1,1))
        self.assertEqual(beat_sync.phase(9,120,0,8,16),(1,1))

    def test_click_and_cache(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'body';root.mkdir()
            sr=11025;audio=np.zeros(sr*20)
            for t in np.arange(.2,20,.5):
                i=int(t*sr);size=min(160,len(audio)-i)
                audio[i:i+size]=.8*np.hanning(size)*np.sin(np.arange(size)*2*np.pi*1000/sr)
            path=Path(d)/'click.wav'
            with wave.open(str(path),'wb') as f:
                f.setnchannels(1);f.setsampwidth(2);f.setframerate(sr)
                f.writeframes((audio*32767).astype('<i2').tobytes())
            with patch.object(beat_sync,'ROOT',root):
                result=beat_sync.analyze(path)
                self.assertLess(abs(result['bpm']-120),5)
                self.assertEqual(beat_sync.analyze(path),result)


if __name__=='__main__':
    unittest.main()
