"""Generate speaking and thinking body assets, preserving the approved reference."""
import copy
import json
from pathlib import Path
import urllib.request
from idle_submit import prompt, API

ROOT = Path(__file__).resolve().parents[1]
TEXTS = {
    'speaking': 'The same illustrated character talks warmly to the viewer. Subtle natural mouth opening and closing, gentle facial expression changes, a tiny nod and quiet breathing. Keep the hands and body pose almost still. Preserve character identity, blue hair, turquoise jacket, black outfit, proportions and futuristic background. Locked camera, stable lighting, no zoom, one continuous shot.',
    'thinking': 'The same illustrated character quietly thinks. Her mouth rests closed, her eyes glance slightly upward, her head tilts just a little and she breathes gently. Calm thoughtful expression, very subtle movement. Keep her hands and body almost still. Preserve character identity, blue hair, turquoise jacket, black outfit, proportions and futuristic background. Locked camera, stable lighting, no zoom, one continuous shot. No talking.',
}

if __name__ == '__main__':
    for index, (action, text) in enumerate(TEXTS.items()):
        workflow = copy.deepcopy(prompt)
        workflow['6']['inputs'].update(width=512, height=768, length=121)
        workflow['10']['inputs']['noise_seed'] = 45 + index
        workflow['3']['inputs']['text'] = text
        workflow['4']['inputs']['text'] = 'camera movement, zoom, cuts, scene change, dancing, walking, large gestures, flickering, brightness changes, face distortion, extra fingers, changing clothes'
        workflow['13']['inputs']['filename_prefix'] = f'Neris-A/{action}_v1'
        (ROOT / f'generation/{action}_api.json').write_text(json.dumps(workflow, indent=2))
        request = urllib.request.Request(API + '/prompt', data=json.dumps({'prompt':workflow}).encode(), headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            print(error.read().decode())
            raise
        (ROOT / f'generation/{action}_job.json').write_text(json.dumps(result, indent=2))
        print(action, json.dumps(result), flush=True)
