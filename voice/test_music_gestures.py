import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'body'))
from gesture_music import Controller
import music_feedback

class GestureTests(unittest.TestCase):
    def setUp(self):self.now=0;self.calls=[];self.song='/music/song.flac'
    def control(self):return Controller(clock=lambda:self.now,execute=lambda a:self.calls.append(a) or True,context=lambda:self.song)
    def test_replay_hold_release_and_once(self):
        c=self.control();self.assertIsNone(c.update({'Number_1'},True));self.now=1
        self.assertEqual(c.update({'Number_1'},True),'replay')
        self.now=2;c.update({'Number_1'},True);self.assertEqual(self.calls,['replay'])
        c.update(set(),True);c.update(set(),True);c.update({'Number_1'},True);self.now=3
        self.assertEqual(c.update({'Number_1'},True),'replay')
    def test_repeat_longer_hold(self):
        c=self.control();c.update({'Number_2'},True);self.now=1
        self.assertIsNone(c.update({'Number_2'},True));self.now=1.5
        self.assertEqual(c.update({'Number_2'},True),'repeat_one')
    def test_no_song_and_disabled_and_ambiguous(self):
        c=self.control();self.song=None;c.update({'Number_1'},True);self.now=1.5
        self.assertIsNone(c.update({'Number_1'},True));self.assertFalse(self.calls)
        self.song='/song';c.update({'Number_1'},False);self.now=3
        self.assertIsNone(c.update({'Number_1','Number_2'},True));self.assertFalse(self.calls)
    def test_context_change_restarts_hold_and_stale_sample(self):
        c=self.control();c.update({'Number_1'},True);self.song='/other';self.now=.7
        c.update({'Number_1'},True);self.now=1.1;self.assertIsNone(c.update({'Number_1'},True))
        self.now=1.8;self.assertEqual(c.update({'Number_1'},True),'replay')
        c=self.control();c.update({'Number_2'},True);self.now=5
        self.assertIsNone(c.update({'Number_2'},True))
    def test_confirmed_feedback_and_repeat_off_is_success(self):
        with patch('gesture_music.music.loaded_track',return_value='/song'),patch('gesture_music.music.toggle_repeat_one',return_value=False),patch('body_bridge.send') as status,patch('music_feedback.enqueue',return_value=True) as voice:
            self.assertTrue(Controller.perform('repeat_one'))
            self.assertEqual(status.call_args.args[0]['text'],'Repeat One · Off');voice.assert_called_once_with('repeat_off')
    def test_replay_ack_failure_not_claimed_success(self):
        with patch('gesture_music.music.loaded_track',return_value='/song'),patch('gesture_music.music.replay',return_value={'ok':False}) as replay,patch('body_bridge.send') as status,patch('music_feedback.enqueue',return_value=True) as voice:
            self.assertFalse(Controller.perform('replay'));replay.assert_called_once_with(require_loaded=True)
            self.assertEqual(status.call_args.args[0]['text'],'Replay · Failed');voice.assert_called_once_with('replay_failed')
    def test_feedback_language_and_unknown(self):
        for key in music_feedback.PHRASES:
            for language in ('zh','en','nan'):self.assertTrue(music_feedback.phrase(key,language))
        self.assertIsNone(music_feedback.phrase('arbitrary','zh'))

if __name__=='__main__':unittest.main()
