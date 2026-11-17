"""Collect V2 idle and build a forward/reverse loop, without changing live actions."""
import hashlib
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeai_config import COMFY_DIR
import json
import shutil
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
NAME='idle_v2_reference_v1'
JOB=json.loads((ROOT/f'generation/{NAME}_job.json').read_text())
RAW=ROOT/f'body/assets/{NAME}.mp4'
LOOP=ROOT/f'body/assets/{NAME}_loop.mp4'

if __name__=='__main__':
    if LOOP.exists():raise SystemExit('Loop exists: reuse/review instead of overwriting')
    for attempt in range(240):
        with urllib.request.urlopen('http://127.0.0.1:8188/history/'+JOB['prompt_id'],timeout=15) as response:
            result=json.load(response).get(JOB['prompt_id'])
        if result:
            (ROOT/f'generation/{NAME}_history.json').write_text(json.dumps(result,indent=2))
            if result.get('status',{}).get('status_str')=='error':raise SystemExit('ComfyUI failed; inspect saved history')
            files=[item for output in result.get('outputs',{}).values() for group in output.values()
                   if isinstance(group,list) for item in group if isinstance(item,dict)
                   and str(item.get('filename','')).endswith('.mp4')]
            if files:
                item=files[0];base=Path(str(COMFY_DIR / 'output')).resolve()
                source=(base/item.get('subfolder','')/item['filename']).resolve()
                if not source.is_relative_to(base):raise ValueError('Unexpected source path')
                shutil.copyfile(source,RAW)
                break
        time.sleep(5)
    else:raise SystemExit('Timed out; inspect job before resubmitting')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(RAW),
        '-filter_complex','[0:v]split=2[f][b];[b]reverse[r];[f][r]concat=n=2:v=1:a=0[v]',
        '-map','[v]','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
        '-movflags','+faststart',str(LOOP)],check=True)
    contact=ROOT/f'generation/{NAME}_contact.jpg'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(LOOP),
        '-vf','fps=1,scale=160:240,tile=4x3','-frames:v','1',str(contact)],check=True)
    metadata=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries',
        'format=duration:stream=width,height,r_frame_rate','-of','json',str(LOOP)],text=True))
    metadata.update({'prompt_id':JOB['prompt_id'],'reference_sha256':JOB['reference_sha256'],
        'asset':str(LOOP),'raw':str(RAW),'contact_sheet':str(contact),
        'construction':'forward plus reversed generation','accepted_by_user':False})
    (ROOT/f'generation/{NAME}_metadata.json').write_text(json.dumps(metadata,indent=2))
    print(json.dumps(metadata,indent=2))
