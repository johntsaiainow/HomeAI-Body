"""Submit a longer, higher-resolution idle candidate without replacing active assets."""
import copy
import json
from pathlib import Path
import urllib.request
from idle_submit import prompt, API

ROOT = Path(__file__).resolve().parents[1]
workflow = copy.deepcopy(prompt)
workflow['6']['inputs'].update(width=512, height=768, length=121)
workflow['3']['inputs']['text'] = (
    'The same illustrated character holds the exact original relaxed pose for the entire shot. '
    'Extremely subtle slow breathing and very slight hair movement. '
    'Keep the face, eyes, hands, clothing, colors, lighting and background stable. '
    'Locked camera. No zoom, no talking, no gestures, no scene change. Calm seamless idle motion.')
workflow['4']['inputs']['text'] += ', brightness changes, color changes, temporal flicker, morphing, moving hands'
workflow['13']['inputs']['filename_prefix'] = 'Neris-A/idle_hq_v2'

if __name__ == '__main__':
    path = ROOT / 'generation/idle_hq_api.json'
    path.write_text(json.dumps(workflow, indent=2))
    request = urllib.request.Request(API + '/prompt',
        data=json.dumps({'prompt': workflow}).encode(),
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        print(error.read().decode())
        raise
    (ROOT / 'generation/idle_hq_job.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
