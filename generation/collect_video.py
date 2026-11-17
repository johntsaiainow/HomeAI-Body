"""Collect a named ComfyUI video candidate; never changes live actions."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeai_config import COMFY_DIR
import json
import re
import shutil
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name')
    args=parser.parse_args();name=args.name
    if not re.fullmatch('[a-z0-9_]+',name):raise SystemExit('Invalid candidate name')
    job=json.loads((ROOT/f'generation/{name}_job.json').read_text())
    target=ROOT/f'body/assets/{name}.mp4'
    if target.exists():raise SystemExit('Candidate exists: inspect/reuse instead of overwriting')
    for attempt in range(240):
        with urllib.request.urlopen('http://127.0.0.1:8188/history/'+job['prompt_id'],timeout=15) as response:
            result=json.load(response).get(job['prompt_id'])
        if result:
            (ROOT/f'generation/{name}_history.json').write_text(json.dumps(result,indent=2))
            if result.get('status',{}).get('status_str')=='error':raise SystemExit('ComfyUI failed; inspect saved history')
            files=[item for output in result.get('outputs',{}).values() for group in output.values()
                   if isinstance(group,list) for item in group if isinstance(item,dict)
                   and str(item.get('filename','')).endswith('.mp4')]
            if files:
                entry=files[0];base=Path(str(COMFY_DIR / 'output')).resolve()
                source=(base/entry.get('subfolder','')/entry['filename']).resolve()
                if not source.is_relative_to(base):raise ValueError('Unexpected source path')
                shutil.copyfile(source,target);break
        time.sleep(5)
    else:raise SystemExit('Timed out; check existing job before resubmitting')
    contact=ROOT/f'generation/{name}_contact.jpg'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(target),
                    '-vf','fps=1,scale=160:240,tile=4x3','-frames:v','1',str(contact)],check=True)
    metadata=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries',
        'format=duration:stream=width,height,r_frame_rate','-of','json',str(target)],text=True))
    metadata.update({'asset':str(target),'reference_sha256':job.get('reference_sha256'),
                     'prompt_id':job['prompt_id'],'contact_sheet':str(contact),'accepted_by_user':False})
    (ROOT/f'generation/{name}_metadata.json').write_text(json.dumps(metadata,indent=2))
    print(json.dumps(metadata,indent=2))
