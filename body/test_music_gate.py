import unittest
from unittest.mock import patch
from music_gate import MusicGate

class MusicGateTests(unittest.TestCase):
    def test_playing_blocks_paused_and_stopped_allow(self):
        gate=MusicGate()
        with patch('music_gate.music.request',side_effect=[{'data':False},{'data':True},None]),patch('music_gate.music.active',return_value=False):
            self.assertTrue(gate.blocked(force=True))
            self.assertFalse(gate.blocked(force=True))
            self.assertFalse(gate.blocked(force=True))
    def test_any_player_path_including_replay_uses_actual_ipc(self):
        gate=MusicGate()
        with patch('music_gate.music.request',return_value={'data':False}) as request:
            self.assertTrue(gate.blocked());self.assertTrue(gate.blocked())
            request.assert_called_once_with(['get_property','pause'])
    def test_forced_result_guard_bypasses_cache(self):
        gate=MusicGate()
        with patch('music_gate.music.request',side_effect=[None,{'data':False}]),patch('music_gate.music.active',return_value=False):
            self.assertFalse(gate.blocked());self.assertTrue(gate.blocked(force=True))
    def test_unresponsive_live_player_blocks_conservatively(self):
        gate=MusicGate()
        with patch('music_gate.music.request',return_value=None),patch('music_gate.music.active',return_value=True):
            self.assertTrue(gate.blocked())

if __name__=='__main__':unittest.main()
