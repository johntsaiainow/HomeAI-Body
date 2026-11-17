"""Collect the submitted candidate without changing the live action library."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeai_config import COMFY_DIR
import shutil
import subprocess
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
VERSION=sys.argv[1] if len(sys.argv)>1 else 'v1'
if VERSION not in ('v1','v2','v3','lower_v1'):raise SystemExit('Unsupported Vulcan candidate version')
JOB=json.loads((ROOT/f'generation/vulcan_{VERSION}_job.json').read_text())
PROMPT_ID=JOB['prompt_id']
STATUS=ROOT/f'generation/vulcan_{VERSION}_status.json'


def save(**state):
    STATUS.write_text(json.dumps({'prompt_id':PROMPT_ID,'updated_at':time.time(),**state},indent=2))


def main():
    save(stage='generating',accepted=False)
    for attempt in range(720):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8188/history/'+PROMPT_ID,timeout=15) as response:
                result=json.load(response).get(PROMPT_ID)
            if result:
                (ROOT/f'generation/vulcan_{VERSION}_history.json').write_text(json.dumps(result,indent=2))
                if result.get('status',{}).get('status_str')=='error':
                    save(stage='failed',reason='ComfyUI execution error; inspect vulcan_v1_history.json',accepted=False)
                    return 1
                outputs=result.get('outputs',{})
                files=[item for output in outputs.values() for group in output.values()
                       if isinstance(group,list) for item in group if isinstance(item,dict)
                       and str(item.get('filename','')).lower().endswith('.mp4')]
                if files:
                    entry=files[0]
                    source_root=Path(str(COMFY_DIR / 'output')).resolve()
                    source=(source_root/entry.get('subfolder','')/entry['filename']).resolve()
                    if not source.is_relative_to(source_root):raise ValueError('Unexpected output path')
                    target=ROOT/f'body/assets/vulcan_salute_{VERSION}_candidate.mp4'
                    shutil.copyfile(source,target)
                    contact=ROOT/f'generation/vulcan_{VERSION}_contact.jpg'
                    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(target),
                        '-vf','fps=2,scale=160:240,tile=4x3','-frames:v','1',str(contact)],check=True)
                    save(stage='candidate_ready',asset=str(target),contact_sheet=str(contact),accepted=False)
                    print('Candidate saved:',target,flush=True)
                    return 0
        except Exception as error:
            print(type(error).__name__,str(error),flush=True)
        time.sleep(5)
    save(stage='timeout',reason='Check ComfyUI job before any resubmission',accepted=False)
    return 1


if __name__=='__main__':raise SystemExit(main())
