"""Isolated listener regression: no microphone, GPU or actual worker."""
import ast
import json
from pathlib import Path
import sys
import time
import types
from unittest.mock import Mock, patch
import numpy as np
from cffi import FFI

class Done(Exception): pass
class Client:
    def close(self): pass
    def transcribe(self,*args): raise AssertionError('Chinese called Whisper')
    def start(self): raise AssertionError('Chinese started Whisper')
class Stream:
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,n):
        ffi=FFI()
        payload=np.full(n,1000,dtype=np.int16).tobytes()
        return ffi.buffer(ffi.new('char[]',payload),len(payload)),False
class Recognizer:
    def __init__(self,*args): self.n=0
    def Reset(self): self.n=0
    def AcceptWaveform(self,data):
        assert isinstance(data,bytes), 'Vosk needs bytes, not a CFFI buffer'
        self.n+=1
        return self.n==6
    def Result(self): return json.dumps({'text':'测试中文'})
    def FinalResult(self): raise AssertionError('Missed streaming endpoint')

queue=Mock()
def put(text):
    assert text=='测试中文'
    raise Done()
queue.put.side_effect=put
source=ast.parse(Path(__file__).with_name('agent.py').read_text())
function=next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='listen_vad_loop')
env=dict(__file__=str(Path(__file__).with_name('agent.py')),Path=Path,Model=lambda path:None,SAMPLE_RATE=16000,BLOCK_SIZE=1600,SILENCE_THRESHOLD=500,SILENCE_DURATION=.65,
         KaldiRecognizer=Recognizer,vosk_model=None,np=np,json=json,time=time,
         speech_service=types.SimpleNamespace(selected=lambda:'zh',backend=lambda language:'auto'),
         sd=types.SimpleNamespace(RawInputStream=lambda **kw:Stream()),
         microphone=types.SimpleNamespace(muted=lambda:False),
         is_playing_audio=types.SimpleNamespace(is_set=lambda:False),
         is_playing_music=types.SimpleNamespace(is_set=lambda:False),
         notify=lambda *args:None,command_queue=queue,cc=types.SimpleNamespace(convert=lambda t:t))
with patch.dict(sys.modules,{'asr_client':types.SimpleNamespace(BreezeClient=Client)}):
    exec(compile(ast.Module(body=[function],type_ignores=[]),'listener-test','exec'),env)
    try: env['listen_vad_loop']()
    except Done: pass
queue.put.assert_called_once()
print('PASS Chinese streams to Vosk without loading or calling Whisper')
queue.reset_mock()
env['speech_service']=types.SimpleNamespace(selected=lambda:'en',backend=lambda language:'vosk')
with patch.dict(sys.modules,{'asr_client':types.SimpleNamespace(BreezeClient=Client)}), patch.object(Path,'is_file',return_value=True):
    try: env['listen_vad_loop']()
    except Done: pass
queue.put.assert_called_once()
print('PASS English uses Vosk streaming when the model is ready')
