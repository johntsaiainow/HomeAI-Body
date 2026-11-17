"""Saved queue tests; live mpv uses isolated socket and null audio only."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import wave
from unittest.mock import patch
import music
import playlist

class QueueTests(unittest.TestCase):
    def test_empty_does_not_stop_current_music(self):
        with patch('playlist.tracks',return_value=[]), patch.object(music,'stop') as stop:
            self.assertEqual(music.play_playlist()['reason'],'empty')
            stop.assert_not_called()
    def test_corrupt_list(self):
        with patch('playlist.tracks',side_effect=ValueError('invalid')), patch.object(music,'stop') as stop:
            self.assertEqual(music.play_playlist()['reason'],'invalid_list')
            stop.assert_not_called()
    def test_next_guard(self):
        with patch.object(music,'request',side_effect=[{'data':0},{'data':1}]) as request:
            self.assertFalse(music.playlist_step(1))
            self.assertEqual(request.call_count,2)
    @unittest.skipUnless(shutil.which('mpv'),'mpv required')
    def test_native_queue_advances_then_exits_and_manual_skip(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            songs=[]
            for name in ('first','second'):
                path=root/(name+'.wav')
                with wave.open(str(path),'wb') as stream:
                    stream.setparams((1,2,8000,0,'NONE','not compressed'))
                    stream.writeframes(b'\x00\x00'*16000)
                songs.append(str(path))
            (root/'list.json').write_text(json.dumps(songs+[str(root/'missing.wav')]))
            real_popen=subprocess.Popen;processes=[]
            def spawn(args,**kwargs):
                process=real_popen([*args,'--ao=null'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**kwargs)
                processes.append(process);return process
            with patch.object(music,'IPC',root/'mpv.sock'), patch.object(music,'LAST',root/'last.json'), patch.object(playlist,'STATE',root/'list.json'), patch.object(music.subprocess,'Popen',side_effect=spawn):
                try:
                    result=music.play_playlist()
                    self.assertTrue(result['ok'],result)
                    self.assertEqual(result['count'],2)
                    self.assertEqual(result['skipped'],1)
                    self.assertEqual(music.loaded_track(),songs[0])
                    self.assertEqual(music.repeat_one(),False)
                    deadline=time.monotonic()+5
                    while time.monotonic()<deadline and music.loaded_track()!=songs[1]:time.sleep(.05)
                    self.assertEqual(music.loaded_track(),songs[1],'EOF must advance to second song')
                    self.assertTrue(music.playlist_step(-1))
                    self.assertTrue(music.playlist_step(1))
                    self.assertFalse(music.playlist_step(1))
                    processes[-1].wait(timeout=5)
                    self.assertFalse(list(root.glob('*.m3u8')))
                finally:
                    for process in processes:
                        if process.poll() is None:process.terminate()
                        process.wait(timeout=3)

if __name__=='__main__':unittest.main()
