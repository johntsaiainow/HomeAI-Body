import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'body'))
import playlist
from gesture_music import Controller

class PlaylistTests(unittest.TestCase):
    def test_save_deduplicate_remove_and_missing(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(playlist, 'STATE', Path(directory)/'list.json'):
            song=Path(directory)/'song.mp3';song.touch()
            self.assertEqual(playlist.change(song), 'added')
            self.assertEqual(playlist.change(song), 'exists')
            self.assertEqual(playlist.tracks(), [str(song)])
            self.assertEqual(playlist.STATE.stat().st_mode & 0o777, 0o600)
            song.unlink()
            self.assertEqual(playlist.change(song, False), 'removed')
            self.assertEqual(playlist.change(song, False), 'absent')
    def test_three_four_hold_release_context_and_disabled(self):
        for gesture, action in [('Number_3','playlist_add'), ('Number_4','playlist_remove')]:
            now=[0];song=['/song'];calls=[]
            c=Controller(clock=lambda:now[0],execute=lambda a:calls.append(a) or True,context=lambda:song[0])
            c.update({gesture}, True);now[0]=1
            self.assertEqual(c.update({gesture}, True), action)
            now[0]=1.5;c.update({gesture},True);self.assertEqual(calls,[action])
            c.update(set(),True);c.update(set(),True)
            song[0]=None;now[0]=2;c.update({gesture},True);now[0]=3
            self.assertIsNone(c.update({gesture},True))
            self.assertIsNone(c.update({gesture},False))
    def test_feedback_after_save_and_no_playback_change(self):
        with patch('gesture_music.music.loaded_track',return_value='/song'), patch('playlist.change',return_value='added') as save, patch('body_bridge.send'), patch('music_feedback.enqueue',return_value=True) as feedback:
            self.assertTrue(Controller.perform('playlist_add'))
            save.assert_called_once_with('/song',add=True)
            feedback.assert_called_once_with('playlist_added')
    def test_corrupt_list_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(playlist,'STATE',Path(directory)/'list.json'):
            playlist.STATE.write_text('broken')
            with self.assertRaises(ValueError):playlist.change('/song',False)
            self.assertEqual(playlist.STATE.read_text(),'broken')

if __name__=='__main__':unittest.main()
