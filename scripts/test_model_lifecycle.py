"""No real model operations in these tests."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import model_lifecycle as lifecycle
import model_router

class SwitchTests(unittest.TestCase):
    def row(self,identifier,status='idle',kind='llm'):
        return {'identifier':identifier,'type':kind,'status':status}
    def test_unload_before_load_and_verify(self):
        rows=[[self.row('old')],[],[self.row('new')]]
        calls=[]
        def run(args):
            calls.append(args)
            return json.dumps(rows.pop(0)) if args==['ps','--json'] else ''
        with patch.object(lifecycle,'run',side_effect=run):lifecycle.prepare('local','neris-a','new')
        self.assertLess(calls.index(['unload','old']), calls.index(['load','new','--identifier','new','--yes']))
    def test_cloud_unloads_but_never_loads_or_touches_embeddings(self):
        with patch.object(lifecycle,'run',side_effect=[json.dumps([self.row('old'),self.row('embed',kind='embedding')]),'',json.dumps([self.row('embed',kind='embedding')])]) as run:
            lifecycle.prepare('online','openai','cloud')
            self.assertEqual(run.call_args_list[1].args[0],['unload','old'])
            self.assertEqual(run.call_count,3)
    def test_same_model_no_reload(self):
        with patch.object(lifecycle,'run',return_value=json.dumps([self.row('new')])) as run:
            lifecycle.prepare('local','neris-a','new');self.assertEqual(run.call_count,1)
    def test_busy_does_not_unload(self):
        with patch.object(lifecycle,'run',return_value=json.dumps([self.row('old','busy')])) as run:
            with self.assertRaises(ValueError):lifecycle.prepare('local','neris-a','new')
            self.assertEqual(run.call_count,1)
    def test_failed_unload_never_loads(self):
        with patch.object(lifecycle,'run',side_effect=[json.dumps([self.row('old')]),ValueError('failed')]) as run:
            with self.assertRaises(ValueError):lifecycle.prepare('local','neris-a','new')
            self.assertFalse(any(call.args[0][0]=='load' for call in run.call_args_list))
    def test_selection_only_saved_after_success(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(model_router,'CONFIG',Path(directory)/'config.json'):
            original={'active':'online','profiles':{'online':{'provider':'openai','model':'cloud'},'local':{'provider':'neris-a','model':'old'}}}
            model_router.CONFIG.write_text(json.dumps(original))
            with patch.object(lifecycle,'prepare',side_effect=ValueError('load failed')):
                with self.assertRaises(ValueError):model_router.select_model('local','neris-a','new')
                self.assertEqual(model_router.load(),original)
            with patch.object(lifecycle,'prepare') as prepare:
                self.assertEqual(model_router.select_model('local','neris-a','new'),('local','neris-a','new'))
                prepare.assert_called_once_with('local','neris-a','new')

if __name__=='__main__':unittest.main()
