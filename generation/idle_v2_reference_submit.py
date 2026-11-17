"""Generate idle from the newly approved neutral V2 reference."""
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
NAME='idle_v2_reference_v1'
if __name__=='__main__':
    job=ROOT/f'generation/{NAME}_job.json'
    if job.exists():raise SystemExit('Existing job: inspect/reuse before generating again')
    reference=ROOT/'Reference.webp'
    shutil.copyfile(reference,str(COMFY_DIR / 'input/neris_idle_v2_reference.webp'))
    shutil.copyfile(reference,ROOT/f'generation/{NAME}_reference.webp')
    workflow=copy.deepcopy(prompt)
    workflow['5']['inputs']['image']='neris_idle_v2_reference.webp'
    workflow['6']['inputs'].update(width=512,height=768,length=121)
    workflow['10']['inputs']['noise_seed']=91
    workflow['3']['inputs']['text']=(
        'The same illustrated blue-haired woman stands in exactly the input pose, both arms relaxed '
        'down at her sides for the entire shot. A small closed-mouth smile. Extremely subtle slow '
        'breathing, one gentle natural blink, barely perceptible hair movement. Keep both hands '
        'completely still and lowered. Preserve the same face, body proportions, glowing turquoise '
        'jacket, dark clothes and teal futuristic background. Fixed camera, fixed composition and '
        'stable lighting. Almost still portrait. No speaking, no gestures, no walking.')
    workflow['4']['inputs']['text']=(
        'raised arms, hand gestures, waving, talking, open mouth, dancing, walking, head turning, '
        'camera motion, zoom, cuts, brightness changes, color changes, flicker, morphing, '
        'face distortion, moving hands, extra fingers, extra limbs')
    workflow['13']['inputs']['filename_prefix']='Neris-A/'+NAME
    (ROOT/f'generation/{NAME}_api.json').write_text(json.dumps(workflow,indent=2))
    req=urllib.request.Request(API+'/prompt',data=json.dumps({'prompt':workflow}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:result=json.load(response)
    result['reference_sha256']=hashlib.sha256(reference.read_bytes()).hexdigest()
    job.write_text(json.dumps(result,indent=2));print(json.dumps(result))
