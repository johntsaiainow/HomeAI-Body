"""Generate a more energetic dance from the approved neutral V2 reference."""
import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeai_config import COMFY_DIR
import hashlib
import json
import shutil
import urllib.request
from idle_submit import prompt,API

ROOT=Path(__file__).resolve().parents[1]
NAME='dancing_v2_dynamic'
if __name__=='__main__':
    job=ROOT/f'generation/{NAME}_job.json'
    if job.exists():raise SystemExit('Existing job: inspect before resubmitting')
    reference=ROOT/'Reference.webp'
    shutil.copyfile(reference,str(COMFY_DIR / 'input/neris_dance_v2_reference.webp'))
    shutil.copyfile(reference,ROOT/f'generation/{NAME}_reference.webp')
    workflow=copy.deepcopy(prompt)
    workflow['5']['inputs']['image']='neris_dance_v2_reference.webp'
    workflow['6']['inputs'].update(width=512,height=768,length=193)
    workflow['10']['inputs']['noise_seed']=104
    workflow['3']['inputs']['text']=(
        'The same illustrated blue-haired woman performs an energetic upbeat pop dance, '
        'not merely swaying. Strong rhythmic hip shifts left and right, pronounced knee bounces, '
        'quick alternating side steps, lively shoulder accents and broad coordinated arm sweeps '
        'across her chest and outward. Clear large movements of arms and torso with confident '
        'musical energy. Her glowing jacket and hair move naturally with the dance. '
        'A cheerful expressive face. Smooth coherent anatomy, one dancer only. '
        'Finish near the starting upright stance with arms lowered. Preserve the same face, '
        'blue hair, turquoise jacket, black outfit and futuristic background. '
        'Fixed camera and steady framing, stable lighting, no cuts, one continuous shot.')
    workflow['4']['inputs']['text']=(
        'standing still, minimal movement, slow gentle swaying, frozen arms, camera movement, '
        'zoom, cuts, scene change, extra arms, extra legs, extra fingers, broken joints, '
        'distorted face, flicker, changing clothes, character outside frame')
    workflow['13']['inputs']['filename_prefix']='Neris-A/'+NAME
    (ROOT/f'generation/{NAME}_api.json').write_text(json.dumps(workflow,indent=2))
    req=urllib.request.Request(API+'/prompt',data=json.dumps({'prompt':workflow}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:result=json.load(response)
    result['reference_sha256']=hashlib.sha256(reference.read_bytes()).hexdigest()
    job.write_text(json.dumps(result,indent=2));print(json.dumps(result))
