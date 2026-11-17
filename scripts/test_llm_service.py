"""Lifecycle tests with mocked LM Studio. Never stops a real server."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import llm_service as llm

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.state=Path(self.temp.name)/'owner.json'
        p=patch.object(llm,'STATE',self.state);p.start();self.addCleanup(p.stop)
        self.cfg={'enabled':True,'cli':sys.executable,'port':1234,'model':'test-model',
                  'autoload_model':True,'stop_owned_server_on_exit':True,'provider':'test'}
        p=patch.object(llm,'config',return_value=self.cfg);p.start();self.addCleanup(p.stop)
        self.identity={'pid':1,'start_ticks':'42','boot_id':'fixture'}
    def test_reuses_existing_without_ownership(self):
        with patch.object(llm,'server_status',return_value={'running':True,'port':1234}),patch.object(llm,'reachable',return_value=True),patch.object(llm,'model_ready',return_value=(True,'ready')),patch.object(llm,'save_owner') as owner,patch.object(llm,'run') as command:
            self.assertTrue(llm.ensure()['model_ready']);owner.assert_not_called();command.assert_not_called()
        self.assertFalse(self.state.exists())
    def test_cold_start_records_and_stops_only_owned_http_server(self):
        with patch.object(llm,'server_status',side_effect=[{'running':False},{'running':True,'port':1234}]),patch.object(llm,'occupied',return_value=False),patch.object(llm,'reachable',return_value=True),patch.object(llm,'daemon_identity',return_value=self.identity),patch.object(llm,'model_ready',return_value=(True,'ready')),patch.object(llm,'run',return_value='') as command:
            self.assertTrue(llm.ensure()['server_ready']);self.assertTrue(self.state.exists())
            self.assertIn(['server','start','--port','1234','--bind','127.0.0.1'],[c.args[1] for c in command.call_args_list])
        with patch.object(llm,'daemon_identity',return_value=self.identity),patch.object(llm,'server_status',side_effect=[{'running':True,'port':1234},{'running':False}]),patch.object(llm,'run') as command:
            self.assertIn('stopped',llm.stop_owned());command.assert_called_once_with(sys.executable,['server','stop'],30)
        self.assertFalse(self.state.exists())
    def test_shared_or_restarted_server_never_stopped(self):
        with patch.object(llm,'run') as command:
            self.assertIn('Pre-existing',llm.stop_owned());command.assert_not_called()
        self.state.write_text(json.dumps({'cli':sys.executable,'port':1234,'identity':self.identity}))
        with patch.object(llm,'daemon_identity',return_value=dict(self.identity,start_ticks='new')),patch.object(llm,'run') as command:
            self.assertIn('left running',llm.stop_owned());command.assert_not_called()
    def test_port_conflict_does_not_take_over(self):
        with patch.object(llm,'server_status',return_value={'running':False}),patch.object(llm,'occupied',return_value=True),patch.object(llm,'run') as command:
            self.assertFalse(llm.ensure()['server_ready']);command.assert_not_called()
    def test_model_load_only_when_no_other_model(self):
        with patch.object(llm,'run',side_effect=['[]','','[{"identifier":"test-model"}]']) as command:
            self.assertTrue(llm.model_ready(self.cfg)[0])
            self.assertEqual(command.call_args_list[1].args[1][0],'load')
        with patch.object(llm,'run',return_value='[{"identifier":"other-model"}]') as command:
            self.assertFalse(llm.model_ready(self.cfg)[0]);self.assertEqual(command.call_count,1)
    def test_disabled_and_model_failure_are_explicit(self):
        self.cfg['enabled']=False
        self.assertFalse(llm.ensure()['server_ready'])
        self.cfg['enabled']=True
        with patch.object(llm,'server_status',return_value={'running':True,'port':1234}),patch.object(llm,'reachable',return_value=True),patch.object(llm,'model_ready',side_effect=RuntimeError('fixture')):
            result=llm.ensure();self.assertTrue(result['server_ready']);self.assertFalse(result['model_ready'])

if __name__=='__main__':unittest.main()
