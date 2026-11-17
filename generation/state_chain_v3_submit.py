"""Submit two-image-guided transition candidates; never changes live actions."""
import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeai_config import COMFY_DIR
import hashlib
import json
import shutil
import urllib.request
from idle_submit import prompt,node,API
ROOT=Path(__file__).resolve().parents[1]
FRAMES=ROOT/'generation/state-chain-v3'
TRANSITIONS=[
 ('listening_v3_transition','idle_first','listening_target','Smoothly settle into the attentive listening pose of the final reference, relaxed lowered arms, small natural facial movement.'),
 ('thinking_v3_transition','listening_target','thinking_target','Smoothly move from attentive listening to the thoughtful hand-to-chin pose of the final reference, natural slow arm and head movement.'),
 ('speaking_v3_entry','thinking_target','speaking_target','Smoothly lower the thinking hand and transition into the speaking pose of the final reference, gentle mouth movement.'),
 ('speaking_v3_return','speaking_target','idle_first','Finish speaking, relax the mouth and return smoothly to the exact neutral idle pose of the final reference.')]
def submit(transitions=TRANSITIONS):
 for name,start,end,motion in transitions:
  job=ROOT/f'generation/{name}_job.json'
  if job.exists():
   print('Existing job, not resubmitting:',name);continue
  for frame in (start,end):
   shutil.copyfile(FRAMES/f'{frame}.png',str(COMFY_DIR / f'input/neris_chain_v3_{frame}.png'))
  w=copy.deepcopy(prompt)
  w['3']['inputs']['text']=('Same blue-haired illustrated woman, same glowing teal jacket, face, clothing, background and camera framing. '+motion+' Continuous natural movement between the two reference images, stable lighting, locked camera, no cut.')
  w['4']['inputs']['text']='camera motion, zoom, cuts, scene change, distorted face, extra fingers, extra limbs, sudden motion, changing clothing, flicker'
  w['5']['inputs']['image']=f'neris_chain_v3_{start}.png'
  w['6']['inputs'].update(width=512,height=768,length=97)
  w['20']=node('LoadImage',image=f'neris_chain_v3_{end}.png')
  w['21']=node('LTXVAddGuide',positive=['6',0],negative=['6',1],vae=['1',2],latent=['6',2],image=['20',0],frame_idx=96,strength=1.0)
  w['7']['inputs'].update(positive=['21',0],negative=['21',1])
  w['10']['inputs'].update(latent_image=['21',2],noise_seed=301+transitions.index((name,start,end,motion)))
  w['22']=node('LTXVCropGuides',positive=['7',0],negative=['7',1],latent=['10',0])
  w['11']['inputs']['samples']=['22',2]
  w['13']['inputs']['filename_prefix']='Neris-A/'+name
  (ROOT/f'generation/{name}_api.json').write_text(json.dumps(w,indent=2))
  req=urllib.request.Request(API+'/prompt',data=json.dumps({'prompt':w}).encode(),headers={'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=30) as response:result=json.load(response)
  result.update({'start_frame':str(FRAMES/f'{start}.png'),'target_frame':str(FRAMES/f'{end}.png'),
      'reference_sha256':hashlib.sha256((FRAMES/f'{start}.png').read_bytes()).hexdigest(),
      'target_sha256':hashlib.sha256((FRAMES/f'{end}.png').read_bytes()).hexdigest(),
      'reference_selection':'Existing V2 state source at 2.0s; idle first decoded frame',
      'accepted_by_user':False})
  job.write_text(json.dumps(result,indent=2));print(name,result['prompt_id'],flush=True)

if __name__=='__main__':submit()
