import ast
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'body'));sys.path.insert(0,str(ROOT/'voice'))
import music_commands

class CommandTests(unittest.TestCase):
    def setUp(self):
        p=patch.object(music_commands.speech_service,'selected',return_value='zh');p.start();self.addCleanup(p.stop)
    def test_replay_synonyms(self):
        with patch.object(music_commands.music,'replay',return_value={'ok':True,'path':'/tmp/Fixture.wav'}) as play:
            for text in ('重播','重播！','再播一次','從頭播放','replay','play again'):
                self.assertIn('Fixture',music_commands.replay_command(text))
            self.assertEqual(play.call_count,6)
    def test_other_text_and_missing_history(self):
        self.assertIsNone(music_commands.replay_command('解釋重播的意思'))
        with patch.object(music_commands.music,'replay',return_value={'ok':False,'reason':'no_track'}):
            self.assertIn('歌曲紀錄',music_commands.replay_command('重播'))
    def test_agent_routes_before_llm_and_song_wait(self):
        source=ast.parse((ROOT/'voice/agent.py').read_text())
        function=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='process_pi_agent_command')
        env={'re':re,'dialogue':lambda *a:None,'notify':lambda *a:None,'waiting_song_until':99999999,'preview_process':None,
             'model_router':SimpleNamespace(handle_command=lambda *a, **kw:None),
             'speech_service':music_commands.speech_service}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'agent-route-test','exec'),env)
        with patch.object(music_commands.music,'replay',return_value={'ok':True,'path':'/tmp/Fixture.wav'}):
            self.assertIn('Fixture',env['process_pi_agent_command']('重播'))
            self.assertEqual(env['waiting_song_until'],0)
        with patch.object(music_commands.music,'play_playlist',return_value={'ok':True,'count':3,'skipped':1}) as play:
            self.assertIn('3 首',env['process_pi_agent_command']('播放音樂清單'))
            play.assert_called_once()
    def test_playlist_commands_and_errors(self):
        with patch.object(music_commands.music,'play_playlist',return_value={'ok':True,'count':2,'skipped':0}) as play:
            for text in ('播放音樂清單','播放音樂選單','播放歌單','play playlist'):
                self.assertIn('2 首',music_commands.playlist_command(text))
            self.assertEqual(play.call_count,4)
        self.assertIsNone(music_commands.playlist_command('什麼是音樂清單'))
        with patch.object(music_commands.music,'play_playlist',return_value={'ok':False,'reason':'empty'}):
            self.assertIn('空的',music_commands.playlist_command('播放歌單'))
        with patch.object(music_commands.music,'playlist_step',return_value=True) as step:
            self.assertIn('已切換',music_commands.playlist_command('下一首'))
            step.assert_called_once_with(1)

if __name__=='__main__':unittest.main()
