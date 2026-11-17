"""Generate a candidate Vulcan salute action; never overwrite approved assets."""
import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeai_config import COMFY_DIR
import json
import shutil
import urllib.request
from idle_submit import prompt, API

ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    job=ROOT/'generation/vulcan_v1_job.json'
    if job.exists():
        raise SystemExit('Job already exists; inspect/reuse it before generating again.')
    shutil.copyfile(ROOT/'Reference.webp',str(COMFY_DIR / 'input/neris_reference.webp'))
    workflow=copy.deepcopy(prompt)
    workflow['6']['inputs'].update(width=512,height=768,length=97)
    workflow['10']['inputs']['noise_seed']=64
    workflow['3']['inputs']['text']=(
        'The same blue-haired illustrated woman performs one clear Vulcan salute. '
        'She gently raises her visible hand beside her shoulder, rotates the palm to face the viewer, '
        'and holds the Star Trek Vulcan greeting: exactly five fingers, index finger and middle finger '
        'touching as one pair, ring finger and little finger touching as a second pair, a wide V-shaped '
        'gap between the middle and ring fingers, thumb extended sideways. '
        'Keep the entire hand inside the frame and clearly visible, not covering her face. '
        'She holds the salute steadily with a friendly smile, then gently returns to the starting pose. '
        'Keep her other hand still. Preserve the reference face, short blue hair, turquoise glowing jacket, '
        'black outfit and futuristic teal background. Static camera, stable lighting, one continuous shot.')
    workflow['4']['inputs']['text']=(
        'ordinary waving, victory sign, peace sign, fist, extra fingers, missing fingers, fused fingers, '
        'extra hands, distorted hand, deformed face, changing clothes, camera movement, zoom, cuts, '
        'flickering, walking, dancing, hand outside frame')
    workflow['13']['inputs']['filename_prefix']='Neris-A/vulcan_salute_v1'
    (ROOT/'generation/vulcan_v1_api.json').write_text(json.dumps(workflow,indent=2))
    req=urllib.request.Request(API+'/prompt',data=json.dumps({'prompt':workflow}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:result=json.load(response)
    job.write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)
