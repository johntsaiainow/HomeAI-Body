"""Generate a closed-eye sleeping body candidate from the user-provided image."""
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
NAME='sleep_v2_reference_v1'
if __name__=='__main__':
    job=ROOT/f'generation/{NAME}_job.json'
    if job.exists():raise SystemExit('Existing sleep job: inspect before resubmitting')
    source=ROOT/'body/assets/sleep_v2.webp'
    shutil.copyfile(source,str(COMFY_DIR / 'input/neris_sleep_v2.webp'))
    shutil.copyfile(source,ROOT/f'generation/{NAME}_reference.webp')
    w=copy.deepcopy(prompt)
    w['5']['inputs']['image']='neris_sleep_v2.webp'
    w['6']['inputs'].update(width=512,height=768,length=121)
    w['10']['inputs']['noise_seed']=121
    w['3']['inputs']['text']=(
        'The same illustrated woman remains asleep in the exact reference pose throughout the shot. '
        'Both eyes stay fully closed at all times. Extremely subtle slow steady breathing in the '
        'shoulders and chest, barely perceptible hair movement. Keep the tilted head, relaxed mouth, '
        'both lowered hands, jacket and body pose still. Preserve the blue hair, face, glowing '
        'turquoise jacket, black clothing, teal background and existing sleep symbols unchanged. '
        'Locked camera, stable lighting, almost still sleeping portrait. No waking up or talking.')
    w['4']['inputs']['text']='open eyes, waking up, blinking, talking, smiling changes, moving hands, raised arms, gestures, head turning, dancing, walking, camera motion, zoom, cuts, flicker, changing text, extra limbs, distorted face'
    w['13']['inputs']['filename_prefix']='Neris-A/'+NAME
    (ROOT/f'generation/{NAME}_api.json').write_text(json.dumps(w,indent=2))
    req=urllib.request.Request(API+'/prompt',data=json.dumps({'prompt':w}).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:result=json.load(response)
    result['reference_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    job.write_text(json.dumps(result,indent=2));print(result)
