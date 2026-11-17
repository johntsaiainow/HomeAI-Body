"""Persistent CPU-only Taigi synthesis worker. JSONL protocol, local cache."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['OMP_NUM_THREADS']='4'
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
protocol=sys.stdout
sys.stdout=sys.stderr  # Third-party diagnostics must not corrupt JSONL.
sys.path[:0]=[str(ROOT/'source'),str(ROOT/'runtime/CosyVoice'),str(ROOT/'runtime/Matcha-TTS')]
CACHE=ROOT.parent/'cache/taigi-tts'
CACHE.mkdir(parents=True,exist_ok=True)
voice=None


def respond(value):
    protocol.write(json.dumps(value,ensure_ascii=False)+'\n');protocol.flush()


def synthesize(text):
    global voice
    if not isinstance(text,str) or not text.strip() or len(text)>120:
        raise ValueError('Taigi synthesis expects 1–120 characters')
    manifest=(ROOT/'source/assets_manifest.json').read_bytes()
    key=hashlib.sha256(b'daily-v1\0'+manifest+text.encode()).hexdigest()
    target=CACHE/(key+'.wav')
    if target.is_file():return {'ok':True,'path':str(target),'cached':True}
    if not (ROOT/'ASSETS_VERIFIED').is_file() or not (ROOT/'model/llm.pt').is_file():
        raise RuntimeError('Taigi model is not ready')
    import numpy as np
    import random
    import soundfile as sf
    import torch
    from taigi_ticket_length_text_20261112_v1 import pronunciation_text
    if voice is None:
        from cosyvoice.cli.cosyvoice import CosyVoice3
        from voice_presets import load_preset
        torch.set_num_threads(4)
        assert not torch.cuda.is_available()
        voice=CosyVoice3(str(ROOT/'model'),fp16=False,load_trt=False,load_vllm=False)
        voice.frontend.spk2info['daily']=load_preset('daily',voice.frontend.device)
    random.seed(1986);np.random.seed(1986);torch.manual_seed(1986)
    model_text,edits=pronunciation_text(text)
    with torch.inference_mode():
        chunks=list(voice.inference_zero_shot(model_text,'','',zero_shot_spk_id='daily',
                                             stream=False,text_frontend=False))
    if not chunks:raise RuntimeError('No Taigi audio generated')
    audio=torch.cat([item['tts_speech'].detach().cpu() for item in chunks],dim=1).squeeze(0).numpy()
    if audio.ndim!=1 or not audio.size or not np.isfinite(audio).all() or not np.any(audio):
        raise RuntimeError('Invalid Taigi audio')
    temporary=target.with_suffix('.wav.tmp')
    sf.write(str(temporary),audio,voice.sample_rate,format='WAV',subtype='PCM_16')
    os.replace(temporary,target)
    return {'ok':True,'path':str(target),'cached':False,'seconds':len(audio)/voice.sample_rate}


respond({'ready':True})
for line in sys.stdin:
    try:
        started=time.monotonic()
        result=synthesize(json.loads(line)['text'])
        result['elapsed_seconds']=round(time.monotonic()-started,3)
        respond(result)
    except Exception as error:
        print(type(error).__name__,str(error),file=sys.stderr,flush=True)
        respond({'ok':False,'error':'Local Taigi synthesis failed; inspect tts-taigi/worker.log'})
