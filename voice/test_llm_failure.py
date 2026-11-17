"""Test agent failure routing without audio, credentials or network."""
import ast
from pathlib import Path
import re
import sys
import subprocess
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'body'),str(ROOT/'voice')]

class FailureTests(unittest.TestCase):
    def agent(self,code,stdout=''):
        tree=ast.parse((ROOT/'voice/agent.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='process_pi_agent_command')
        import llm_metrics
        metrics=Mock();metrics.ModelUnavailableError=llm_metrics.ModelUnavailableError
        metrics.parse_result.side_effect=ValueError('No completed assistant message')
        run=Mock(return_value=SimpleNamespace(returncode=code,stdout=stdout,stderr='private diagnostic'))
        env=dict(re=re,time=time,Path=Path,dialogue=lambda *a:None,notify=lambda *a:None,
                 waiting_song_until=0,preview_process=None,AGENT_WORK_DIR=str(ROOT),
                 model_router=SimpleNamespace(handle_command=lambda *a,**kw:None,pi_command=lambda p:['pi','test']),
                 speech_service=SimpleNamespace(selected=lambda:'zh',instruction=lambda lang:''),
                 subprocess=SimpleNamespace(run=run,TimeoutExpired=subprocess.TimeoutExpired),
                 llm_metrics=metrics,update_llm_failure=Mock(),localized=lambda zh,en:zh)
        exec(compile(ast.Module(body=[function],type_ignores=[]),'llm-failure-test','exec'),env)
        return env,metrics
    def test_nonzero_never_parsed_as_reply(self):
        env,metrics=self.agent(1)
        result=env['process_pi_agent_command']('你好嗎')
        self.assertIn('登入',result)
        self.assertIn('沒有自動切換',result)
        metrics.parse_result.assert_not_called()
        env['update_llm_failure'].assert_called_with('Request failed')
    def test_unavailable_model_explained(self):
        env,metrics=self.agent(0)
        metrics.parse_result.side_effect=metrics.ModelUnavailableError('rejected')
        result=env['process_pi_agent_command']('你好嗎')
        self.assertIn('目前帳號無法使用',result)
        env['update_llm_failure'].assert_called_with('Model unavailable')
    def test_service_failure_explained(self):
        env,metrics=self.agent(0)
        metrics.parse_result.side_effect=RuntimeError('Pi request failed')
        result=env['process_pi_agent_command']('你好嗎')
        self.assertIn('AI 服務未能完成',result)
        self.assertNotIn('Pi request failed',result)
    def test_missing_reply_explained_without_raw_exception(self):
        env,metrics=self.agent(0)
        result=env['process_pi_agent_command']('你好嗎')
        self.assertIn('完整回答',result)
        self.assertNotIn('No completed',result)
        env['update_llm_failure'].assert_called_with('No response')

if __name__=='__main__':unittest.main()
