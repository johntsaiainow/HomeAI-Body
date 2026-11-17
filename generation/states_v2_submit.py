"""Generate V2 listening/thinking/speaking candidates without changing live actions."""
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
TEXTS={
 'listening':('The same illustrated woman listens attentively to the viewer. Her mouth remains closed '
              'in a small smile, a tiny head tilt and a very gentle nod, subtle breathing and one blink. '
              'Keep both arms relaxed down at her sides, hands completely still.'),
 'thinking':('The same illustrated woman quietly thinks. Her mouth stays closed with a thoughtful '
             'gentle smile, her eyes glance slightly upward and her head tilts only a little. '
             'Subtle breathing, very small natural motion. Both arms remain relaxed down at her sides; '
             'no touching the face or lifting a hand.'),
 'speaking':('The same illustrated woman talks warmly to the viewer. Small natural mouth opening '
             'and closing, a friendly expression and a tiny conversational head nod. '
             'Subtle breathing. Both arms remain relaxed down at her sides, hands completely still.')
}
if __name__=='__main__':
    reference=ROOT/'Reference.webp'
    shutil.copyfile(reference,str(COMFY_DIR / 'input/neris_states_v2_reference.webp'))
    shutil.copyfile(reference,ROOT/'generation/states_v2_reference.webp')
    for index,(action,text) in enumerate(TEXTS.items()):
        name=action+'_v2_reference_v1';job=ROOT/f'generation/{name}_job.json'
        if job.exists():
            print('Existing job, reuse:',name,flush=True);continue
        workflow=copy.deepcopy(prompt)
        workflow['5']['inputs']['image']='neris_states_v2_reference.webp'
        workflow['6']['inputs'].update(width=512,height=768,length=121)
        workflow['10']['inputs']['noise_seed']=112+index
        workflow['3']['inputs']['text']=text+(
            ' Preserve the reference face, short blue hair, turquoise glowing jacket, black outfit, '
            'body proportions and teal futuristic background. Fixed camera, stable lighting, '
            'no zoom, no scene change, almost still portrait.')
        workflow['4']['inputs']['text']=(
            'raised hands, raised arms, hand gestures, waving, walking, dancing, large motion, '
            'camera movement, zoom, cuts, changing clothes, face distortion, extra fingers, '
            'extra limbs, flickering, brightness changes')
        if action!='speaking':workflow['4']['inputs']['text']+=', talking, open mouth'
        workflow['13']['inputs']['filename_prefix']='Neris-A/'+name
        (ROOT/f'generation/{name}_api.json').write_text(json.dumps(workflow,indent=2))
        req=urllib.request.Request(API+'/prompt',data=json.dumps({'prompt':workflow}).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as response:result=json.load(response)
        result['reference_sha256']=hashlib.sha256(reference.read_bytes()).hexdigest()
        job.write_text(json.dumps(result,indent=2));print(name,json.dumps(result),flush=True)
