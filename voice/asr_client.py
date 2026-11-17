"""Owns a reusable ASR subprocess; stage-one dependencies remain untouched."""
import base64
import json
from pathlib import Path
import select
import subprocess
import threading

ROOT = Path(__file__).resolve().parents[1]


class BreezeClient:
    def __init__(self):
        self.process = None
        self.lock = threading.Lock()
        self.log = None

    def response(self, timeout):
        if not select.select([self.process.stdout], [], [], timeout)[0]:
            raise TimeoutError('ASR response timed out')
        line=self.process.stdout.readline()
        if not line:
            raise RuntimeError('ASR worker exited')
        return json.loads(line)

    def start(self):
        if self.process is not None and self.process.poll() is None:
            return
        self.log=(ROOT/'asr/worker.log').open('a')
        self.process=subprocess.Popen(
            [str(ROOT/'asr/.venv/bin/python'),'-B','-u',str(ROOT/'asr/worker.py')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,
            text=True,bufsize=1)
        if not self.response(60).get('ready'):
            raise RuntimeError('ASR model not ready')

    def transcribe(self, pcm, language='zh'):
        if language == 'en' and not (ROOT/'models/whisper-tiny.en/DOWNLOAD_COMPLETE').exists():
            raise RuntimeError('English ASR model is not ready; download pending')
        with self.lock:
            try:
                self.start()
                self.process.stdin.write(json.dumps({'pcm':base64.b64encode(pcm).decode(), 'language':language})+'\n')
                self.process.stdin.flush()
                result=self.response(45)
                if not result.get('ok'):
                    raise RuntimeError(result.get('error','ASR failed'))
                return result
            except Exception:
                self.close()
                raise

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            self.process=None
        if self.log:
            self.log.close()
            self.log=None
