import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import music

class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.song=self.root/'Fixture.wav';self.song.touch()
        for name,value in [('LAST',self.root/'last.json'),('_remembered',None)]:
            p=patch.object(music,name,value);p.start();self.addCleanup(p.stop)
    def test_active_seek_and_resume_acknowledged(self):
        def request(args):
            if args==['get_property','path']:return {'data':str(self.song)}
            if args==['get_property','time-pos']:return {'data':0.1}
            if args==['get_property','pause']:return {'data':False}
            return {'error':'success'}
        with patch.object(music,'request',side_effect=request) as ipc,patch.object(music,'play') as play:
            self.assertTrue(music.replay()['ok']);play.assert_not_called()
            ipc.assert_any_call(['seek',0,'absolute+exact']);ipc.assert_any_call(['set_property','pause',False])
        self.assertEqual(music.last_track(),str(self.song))
    def test_finished_song_relaunches_last_saved_track(self):
        music.remember(self.song);started=[False]
        def request(args):
            if not started[0]:return None
            return {'data':str(self.song) if args[-1]=='path' else False if args[-1]=='pause' else 0.1}
        with patch.object(music,'request',side_effect=request),patch.object(music,'play',side_effect=lambda p:started.__setitem__(0,True)) as launch:
            self.assertTrue(music.replay()['ok']);launch.assert_called_once_with(str(self.song))
    def test_no_history_does_not_claim_success(self):
        with patch.object(music,'request',return_value=None),patch.object(music,'play') as launch:
            self.assertEqual(music.replay()['reason'],'no_track');launch.assert_not_called()
    def test_rejected_seek_not_claimed_as_success(self):
        with patch.object(music,'request',side_effect=[{'data':str(self.song)},None]):
            self.assertFalse(music.replay()['ok'])

if __name__=='__main__':unittest.main()
