"""Generate a listening action candidate, keeping the approved character reference."""
import copy
import json
import urllib.request
from pathlib import Path
from idle_submit import prompt, API

ROOT = Path(__file__).resolve().parents[1]
workflow = copy.deepcopy(prompt)
workflow['6']['inputs'].update(width=512, height=768, length=121)
workflow['10']['inputs']['noise_seed'] = 43
workflow['3']['inputs']['text'] = (
    'The same illustrated character is quietly listening to someone in front of her. '
    'Her mouth gently closes into a relaxed attentive expression. A very slight head tilt, '
    'subtle breathing and one small slow nod. Keep hands and body in the original pose. '
    'Preserve the exact character design, face, outfit, proportions, colors and background. '
    'Locked camera, no zoom, very small natural motion. No speaking.')
workflow['4']['inputs']['text'] = (
    'talking, lip movements, dancing, walking, large gestures, camera movement, zoom, '
    'flickering, brightness changes, face morphing, distorted hands, extra fingers, scene change')
workflow['13']['inputs']['filename_prefix'] = 'Neris-A/listening_v1'

if __name__ == '__main__':
    (ROOT / 'generation/listening_api.json').write_text(json.dumps(workflow, indent=2))
    request = urllib.request.Request(API + '/prompt',
        data=json.dumps({'prompt': workflow}).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        print(error.read().decode())
        raise
    (ROOT / 'generation/listening_job.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
