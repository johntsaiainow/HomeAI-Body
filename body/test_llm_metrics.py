import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import llm_metrics as metrics

class MetricsTests(unittest.TestCase):
    def message(self,text='Fixture',**usage):
        return {'role':'assistant','provider':'fixture','model':'fixture-model','stopReason':'stop',
                'content':[{'type':'thinking','thinking':'Not spoken'},{'type':'text','text':text}],
                'usage':usage}
    def test_authoritative_events_no_duplicate_agent_end(self):
        message=self.message(input=10,output=5,totalTokens=15,cacheRead=0,cacheWrite=0,cost={'total':.01})
        lines=[{'type':'message_end','message':message},{'type':'agent_end','messages':[message]}]
        text,data=metrics.parse_result('\n'.join(map(json.dumps,lines)),2)
        self.assertEqual(text,'Fixture');self.assertEqual(data['total'],15)
        self.assertEqual(data['effective_rate'],2.5);self.assertEqual(data['estimated_cost'],.01)
    def test_multiturn_usage_and_reasoning_not_double_counted(self):
        events=[{'type':'message_end','message':self.message(input=10,output=5,reasoning=3,totalTokens=15)},
                {'type':'message_end','message':self.message('Final',input=20,output=7,totalTokens=27,cacheRead=4)}]
        text,data=metrics.parse_result('\n'.join(map(json.dumps,events)),4)
        self.assertEqual(text,'Final');self.assertEqual(data['output'],12);self.assertEqual(data['calls'],2)
        self.assertEqual(data['cache_read'],4)
    def test_zero_unknown_usage_not_fabricated(self):
        _,data=metrics.parse_result(json.dumps({'type':'message_end','message':self.message(input=0,output=0,totalTokens=0,cost={'total':0})}),1)
        self.assertFalse(data['usage_available']);self.assertIsNone(data['input']);self.assertIsNone(data['estimated_cost'])
    def test_unicode_line_separator_and_malformed_record(self):
        line=json.dumps({'type':'message_end','message':self.message('A\u2028B',output=2)},ensure_ascii=False)
        text,_=metrics.parse_result('diagnostic\n[]\n'+line,1)
        self.assertEqual(text,'A\u2028B')
    def test_errors_not_spoken_as_json(self):
        bad=self.message();bad['stopReason']='error'
        with self.assertRaises(RuntimeError):metrics.parse_result(json.dumps({'type':'message_end','message':bad}),1)
        with self.assertRaises(ValueError):metrics.parse_result('not json',1)
    def test_store_excludes_secrets_and_content(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(metrics,'STATE',Path(directory)/'metrics.json'):
            metrics.store({'provider':'fixture','model':'x','apiKey':'DO_NOT_STORE','prompt':'PRIVATE','output':3})
            data=metrics.read();self.assertNotIn('apiKey',data);self.assertNotIn('prompt',data)

if __name__=='__main__':unittest.main()
