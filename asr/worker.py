"""Persistent local ASR worker: JSON lines on stdin/stdout, diagnostics on stderr."""
import base64
import json
from pathlib import Path
import sys
import time
import zlib
import numpy as np
import torch
from transformers import WhisperProcessor, WhisperForConditionalGeneration

torch.set_num_threads(4)
MODEL = Path(__file__).resolve().parents[1] / 'models/Breeze-ASR-26'
# Load only the selected backend. English must not allocate Breeze's VRAM.
processor = None
model = None
english_model = None
english_processor = None
print(json.dumps({'ready':True}), flush=True)
for line in sys.stdin:
    try:
        request = json.loads(line)
        started = time.monotonic()
        audio = np.frombuffer(base64.b64decode(request['pcm'], validate=True), dtype='<i2').astype(np.float32)/32768
        if len(audio)<8000 or len(audio)>16000*30 or float(np.sqrt(np.mean(audio**2)))<.004:
            print(json.dumps({'ok':True,'text':'','rejected':'audio_gate'}),flush=True)
            continue
        language = request.get('language', 'zh')
        active_model, active_processor = model, processor
        if language == 'en':
            english_path = MODEL.parent / 'whisper-tiny.en'
            if not (english_path / 'DOWNLOAD_COMPLETE').exists():
                raise ValueError('English ASR model is not ready; download pending')
            if english_model is None:
                english_processor = WhisperProcessor.from_pretrained(str(english_path), local_files_only=True)
                english_model = WhisperForConditionalGeneration.from_pretrained(
                    str(english_path), local_files_only=True, dtype=torch.float32).to('cpu').eval()
                if torch.cuda.is_available() and torch.cuda.mem_get_info()[0] > 1024**3:
                    try:
                        english_model.to(device='cuda', dtype=torch.float16)
                    except torch.cuda.OutOfMemoryError:
                        english_model.to(device='cpu', dtype=torch.float32)
                        torch.cuda.empty_cache()
                print(f'English ASR device: {english_model.device}', file=sys.stderr, flush=True)
            active_model, active_processor = english_model, english_processor
        else:
            if model is None:
                processor = WhisperProcessor.from_pretrained(str(MODEL), local_files_only=True)
                model = WhisperForConditionalGeneration.from_pretrained(
                    str(MODEL), local_files_only=True, dtype=torch.float16).to('cuda').eval()
            active_model, active_processor = model, processor
        features = active_processor(audio, sampling_rate=16000, return_tensors='pt',return_attention_mask=True)
        with torch.inference_mode():
            result = active_model.generate(features.input_features.to(active_model.device,dtype=active_model.dtype),
                attention_mask=features.attention_mask.to(active_model.device), max_new_tokens=128,
                do_sample=False, return_dict_in_generate=True,output_scores=True)
            scores = active_model.compute_transition_scores(result.sequences,result.scores,normalize_logits=True)
        text = active_processor.batch_decode(result.sequences,skip_special_tokens=True)[0].strip()
        logprob = float(scores.mean()) if scores.numel() else -100
        encoded=text.encode()
        compression=len(encoded)/max(1,len(zlib.compress(encoded)))
        rejected = logprob < -1.0 or compression > 2.4 or len(text)<2
        print(json.dumps({'ok':True,'text':'' if rejected else text,
                          'logprob':logprob,'elapsed_seconds':round(time.monotonic()-started,3),
                          'device':str(active_model.device),'rejected':'confidence_gate' if rejected else None},ensure_ascii=False),flush=True)
    except Exception as error:
        print(json.dumps({'ok':False,'error':str(error)}),flush=True)
