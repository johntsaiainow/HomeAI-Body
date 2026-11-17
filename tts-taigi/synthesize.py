"""Local CPU-only Taigi experiment. No microphone upload or voice-clone input."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parent
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ.setdefault('OMP_NUM_THREADS','2')
os.environ.setdefault('HF_HUB_OFFLINE','1')
os.environ.setdefault('TRANSFORMERS_OFFLINE','1')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--text',default='食飽未？你今仔日想欲聽啥物歌？')
    parser.add_argument('--output',type=Path,default=ROOT/'samples/taigi_first.wav')
    parser.add_argument('--preset',choices=['daily','narration'],default='daily')
    args=parser.parse_args()
    if not (ROOT/'DEPENDENCIES_READY').is_file() or not (ROOT/'ASSETS_VERIFIED').is_file():
        raise SystemExit('Installation or verified asset download is not complete. Check install.log and download.log.')
    text=args.text.strip()
    if not text or len(text)>120:raise SystemExit('Please use 1–120 characters for the experiment.')
    sys.path[:0]=[str(ROOT/'source'),str(ROOT/'runtime/CosyVoice'),str(ROOT/'runtime/Matcha-TTS')]
    import torch
    import soundfile as sf
    from safetensors.torch import load_file
    import engine
    from taigi_ticket_length_text_20261112_v1 import pronunciation_text
    assert not torch.cuda.is_available(), 'This first experiment must not occupy the GPU'
    engine.MODEL=ROOT/'model'
    target=engine.MODEL/'llm.pt'
    if not target.is_file():
        print('Converting verified safetensors into local weights-only checkpoint...',flush=True)
        state=load_file(str(engine.MODEL/'merged_llm.safetensors'),device='cpu')
        temporary=target.with_suffix('.pt.tmp')
        torch.save(state,temporary)
        os.replace(temporary,target)
        del state;gc.collect()
    converted,changes=pronunciation_text(text)
    started=time.monotonic()
    print('Synthesizing locally on CPU, preset:',args.preset,flush=True)
    audio=engine.run_model(converted,'','',1986,require_gpu=False,preset_profile=args.preset)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    sf.write(str(args.output),audio,24000,subtype='PCM_16')
    with args.output.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    info={'text':text,'pronunciation_text':converted,'pronunciation_changes':changes,
          'preset':args.preset,'sample_rate':24000,'seconds':len(audio)/24000,
          'elapsed_seconds':time.monotonic()-started,'sha256':digest,
          'research_only':True,'accepted_by_user':False}
    args.output.with_suffix('.json').write_text(json.dumps(info,ensure_ascii=False,indent=2))
    print(json.dumps(info,ensure_ascii=False),flush=True)
    print('Saved:',args.output,flush=True)


if __name__=='__main__':main()
