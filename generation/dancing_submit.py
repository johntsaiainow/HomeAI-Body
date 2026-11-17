"""Generate an eight-second Neris dance candidate without changing active assets."""
import copy
import json
import urllib.request
from pathlib import Path
from idle_submit import prompt, API

ROOT = Path(__file__).resolve().parents[1]
workflow = copy.deepcopy(prompt)
workflow['6']['inputs'].update(width=512, height=768, length=193)
workflow['10']['inputs']['noise_seed'] = 44
workflow['3']['inputs']['text'] = (
    'The same illustrated character performs a cheerful gentle rhythmic dance. '
    'She sways her shoulders and upper body from side to side, softly moves her arms '
    'and nods her head to a steady beat. Smooth relaxed coordinated movements. '
    'Keep the original framing, character identity, blue hair, face, turquoise jacket, '
    'black outfit, proportions and futuristic background consistent. '
    'Fixed camera, no zoom, no cuts, one continuous shot. No spinning or jumping.')
workflow['4']['inputs']['text'] = (
    'camera movement, zoom, scene change, spinning, jumping, exaggerated motion, '
    'extra arms, extra fingers, distorted hands, face morphing, flicker, changing clothes')
workflow['13']['inputs']['filename_prefix'] = 'Neris-A/dancing_v1'

if __name__ == '__main__':
    (ROOT / 'generation/dancing_api.json').write_text(json.dumps(workflow, indent=2))
    request = urllib.request.Request(API + '/prompt',
        data=json.dumps({'prompt': workflow}).encode(), headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        print(error.read().decode())
        raise
    (ROOT / 'generation/dancing_job.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
