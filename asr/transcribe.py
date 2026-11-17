"""Standalone local-only Breeze ASR26 inference; never replaces running voice agent."""
import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'models/Breeze-ASR-26'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('audio', nargs='?')
    parser.add_argument('--smoke', action='store_true', help='Run silence only to test inference, not accuracy')
    parser.add_argument('--device', choices=['cuda','cpu'], default='cuda')
    args = parser.parse_args()
    import numpy as np
    import torch
    from transformers import WhisperProcessor, WhisperForConditionalGeneration
    start = time.monotonic()
    print('Loading local Breeze ASR26…', flush=True)
    processor = WhisperProcessor.from_pretrained(str(MODEL), local_files_only=True)
    model = WhisperForConditionalGeneration.from_pretrained(
        str(MODEL), local_files_only=True,
        dtype=torch.float16 if args.device == 'cuda' else torch.float32).to(args.device)
    model.eval()
    print('MODEL_READY', flush=True)
    if args.smoke:
        audio = np.zeros(16000 * 2, dtype=np.float32)
    elif args.audio:
        result = subprocess.run(['ffmpeg','-v','error','-i',args.audio,'-t','30',
                                 '-ac','1','-ar','16000','-f','f32le','pipe:1'],
                                capture_output=True, check=True, timeout=60)
        audio = np.frombuffer(result.stdout, dtype='<f4').copy()
        if not len(audio):
            raise ValueError('Empty audio')
    else:
        parser.error('Provide audio path or --smoke')
    if not args.smoke and float(np.sqrt(np.mean(audio.astype(np.float64) ** 2))) < 0.002:
        print(json.dumps({'test':'audio_transcription','text':'','status':'too_quiet',
                          'warning':'Audio below energy threshold; no transcription attempted.'}))
        return
    inputs = processor(audio, sampling_rate=16000, return_tensors='pt', return_attention_mask=True)
    features = inputs.input_features.to(device=args.device, dtype=model.dtype)
    with torch.inference_mode():
        tokens = model.generate(features, attention_mask=inputs.attention_mask.to(args.device),
                                max_new_tokens=128, do_sample=False)
    text = processor.batch_decode(tokens, skip_special_tokens=True)[0]
    output = {'test': 'silence_smoke' if args.smoke else 'audio_transcription',
              'text': text, 'device':args.device, 'elapsed_seconds':round(time.monotonic()-start,2)}
    if args.smoke:
        output['warning'] = 'Silence only: verifies execution, not recognition accuracy. Any generated text may be hallucination.'
    print(json.dumps(output, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
