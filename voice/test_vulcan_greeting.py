import ast
from pathlib import Path
import types
import unittest
from unittest.mock import Mock, patch
from gesture_music import Controller


class GreetingTests(unittest.TestCase):
    def test_language_specific_reply(self):
        from vulcan_greeting import reply
        self.assertEqual(reply('zh')['text'],'願你平安長壽。')
        self.assertEqual(reply('en')['text'],'Peace and long life.')
        self.assertTrue(reply('en')['force_english'])
        self.assertEqual(reply('nan')['text'],'祝你平安閣長壽。')
        self.assertFalse(reply('nan')['force_english'])

    def test_cached_taigi_skips_piper_and_preserves_file(self):
        import os
        import tempfile
        tree=ast.parse(Path(__file__).with_name('agent.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='offline_speak')
        process=Mock();process.poll.return_value=0
        subprocess=Mock();subprocess.Popen.return_value=process
        env={'clean_text_for_tts':lambda t:t,'dialogue':Mock(),'notify':Mock(),
             'speech_service':types.SimpleNamespace(selected=lambda:'nan'),
             'voice_output':types.SimpleNamespace(enabled=lambda:True),
             'split_zh_en_segments':lambda t:[('zh',t)],'is_playing_audio':Mock(),
             'tempfile':tempfile,'os':os,'subprocess':subprocess,'time':Mock()}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'tts-cache-test','exec'),env)
        with tempfile.TemporaryDirectory() as folder:
            cached=Path(folder)/'cached.wav';cached.write_bytes(b'fixture')
            env['offline_speak']('祝你平安閣長壽。',body_action='vulcan_salute',audio_file=str(cached))
            self.assertEqual(cached.read_bytes(),b'fixture')
            subprocess.run.assert_not_called()
            self.assertIn(str(cached),subprocess.Popen.call_args.args[0])
            env['notify'].assert_called_once_with('vulcan_salute')
            env['notify'].reset_mock();subprocess.reset_mock()
            synthesize=Mock(return_value=[str(cached)])
            with patch.dict('sys.modules',{
                'taigi_tts_client':types.SimpleNamespace(synthesize=synthesize),
                'body_bridge':types.SimpleNamespace(status=Mock())}):
                env['offline_speak']('今仔日天氣真好。',body_action='vulcan_salute')
            synthesize.assert_called_once_with('今仔日天氣真好。')
            subprocess.run.assert_not_called()
            self.assertEqual(cached.read_bytes(),b'fixture')

    def test_hold_once_and_release(self):
        now=[10.]
        execute=Mock(return_value=True)
        control=Controller(clock=lambda:now[0],execute=execute,mapping={'Vulcan_Salute':'greet'})
        for t in (10.,10.6,11.2,11.8,12.4):
            now[0]=t;control.update({'Vulcan_Salute'},True)
        execute.assert_called_once_with('greet')
        for t in (13.,13.6):now[0]=t;control.update(set(),True)
        for t in (14.,14.6,15.2):now[0]=t;control.update({'Vulcan_Salute'},True)
        self.assertEqual(execute.call_count,2)

    def test_gesture_control_off(self):
        execute=Mock()
        control=Controller(execute=execute,mapping={'Vulcan_Salute':'greet'})
        control.update({'Vulcan_Salute'},False)
        execute.assert_not_called()

    def test_output_off_keeps_text_and_salute_even_in_taigi_mode(self):
        tree=ast.parse(Path(__file__).with_name('agent.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='offline_speak')
        dialogue,notify=Mock(),Mock()
        env={'clean_text_for_tts':lambda t:t,'dialogue':dialogue,'notify':notify,
             'speech_service':types.SimpleNamespace(selected=lambda:'nan'),
             'voice_output':types.SimpleNamespace(enabled=lambda:False)}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'tts-test','exec'),env)
        env['offline_speak']('Peace and long life.',body_action='vulcan_salute',force_english=True)
        dialogue.assert_called_once_with('assistant','Peace and long life.')
        notify.assert_called_once_with('vulcan_salute')


if __name__=='__main__':unittest.main()
