"""Own one persistent local CPU TTS subprocess; no network inference."""
import atexit
import json
from pathlib import Path
import re
import select
import subprocess
import threading

ROOT=Path(__file__).resolve().parents[1]


def chunks(text,limit=80):
    if not text.strip() or len(text)>600:raise ValueError('Taigi reply too long; text retained')
    pending=''
    for sentence in re.split(r'(?<=[。！？!?；;])',text):
        if len(pending)+len(sentence)>limit and pending:
            yield pending;pending=''
        while len(sentence)>limit:
            yield sentence[:limit];sentence=sentence[limit:]
        pending+=sentence
    if pending:yield pending


class TaigiClient:
    def __init__(self):
        self.process=None;self.log=None;self.lock=threading.Lock()
        atexit.register(self.close)

    def response(self,timeout):
        if not select.select([self.process.stdout],[],[],timeout)[0]:raise TimeoutError('Taigi TTS timed out')
        line=self.process.stdout.readline()
        if not line:raise RuntimeError('Taigi TTS worker exited')
        return json.loads(line)

    def start(self):
        if self.process is not None and self.process.poll() is None:return
        self.close()
        self.log=(ROOT/'tts-taigi/worker.log').open('a')
        self.process=subprocess.Popen([str(ROOT/'tts-taigi/.venv/bin/python'),'-u',str(ROOT/'tts-taigi/worker.py')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,bufsize=1)
        if not self.response(30).get('ready'):raise RuntimeError('Taigi TTS not ready')

    def synthesize(self,text):
        with self.lock:
            try:
                pieces=list(chunks(text))
                self.start();files=[]
                for piece in pieces:
                    self.process.stdin.write(json.dumps({'text':piece},ensure_ascii=False)+'\n')
                    self.process.stdin.flush()
                    result=self.response(300)
                    if not result.get('ok'):raise RuntimeError(result.get('error','Taigi TTS failed'))
                    path=Path(result['path']).resolve()
                    if not path.is_relative_to((ROOT/'cache/taigi-tts').resolve()) or not path.is_file():
                        raise RuntimeError('Unexpected Taigi audio path')
                    print('Taigi TTS:',result,flush=True)
                    files.append(str(path))
                return files
            except Exception:
                self.close();raise

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
            self.process=None
        if self.log:self.log.close();self.log=None


_client=None

def synthesize(text):
    global _client
    if _client is None:_client=TaigiClient()
    return _client.synthesize(text)
