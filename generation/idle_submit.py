"""Submit a small LTX image-to-video test; never replaces active body assets."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeai_config import COMFY_DIR
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
API = 'http://127.0.0.1:8188'


def node(kind, **inputs):
    return {'class_type': kind, 'inputs': inputs}


prompt = {
 '1': node('CheckpointLoaderSimple', ckpt_name='ltxv-2b-0.9.8-distilled-fp8.safetensors'),
 '2': node('CLIPLoader', clip_name='t5xxl_fp8_e4m3fn.safetensors', type='ltxv', device='cpu'),
 '3': node('CLIPTextEncode', clip=['2',0], text='The character in the reference image remains in the same relaxed pose. Very subtle natural breathing, a gentle single blink, slight natural movement of hair. Preserve the same face, outfit, body proportions, background and composition. Static camera, no camera movement, calm idle animation, minimal motion.'),
 '4': node('CLIPTextEncode', clip=['2',0], text='camera movement, walking, dancing, large motion, talking, distorted face, extra limbs, flickering, scene change'),
 '5': node('LoadImage', image='neris_reference.webp'),
 '6': node('LTXVImgToVideo', positive=['3',0], negative=['4',0], vae=['1',2], image=['5',0], width=320, height=480, length=49, batch_size=1, strength=1.0),
 '7': node('LTXVConditioning', positive=['6',0], negative=['6',1], frame_rate=24.0),
 '8': node('KSamplerSelect', sampler_name='euler'),
 '9': node('LTXVScheduler', steps=8, max_shift=2.05, base_shift=.95, stretch=True, terminal=.1, latent=['6',2]),
 '10': node('SamplerCustom', model=['1',0], add_noise=True, noise_seed=42, cfg=1.0, positive=['7',0], negative=['7',1], sampler=['8',0], sigmas=['9',0], latent_image=['6',2]),
 '11': node('VAEDecode', samples=['10',0], vae=['1',2]),
 '12': node('CreateVideo', images=['11',0], fps=24.0),
 '13': node('SaveVideo', video=['12',0], filename_prefix='Neris-A/idle_test', format='mp4'),
}

if __name__ == '__main__':
    target = Path(str(COMFY_DIR / 'input/neris_reference.webp'))
    shutil.copyfile(ROOT / 'Reference.webp', target)
    (ROOT / 'generation/idle_api.json').write_text(json.dumps(prompt, indent=2))
    request = urllib.request.Request(API + '/prompt', data=json.dumps({'prompt': prompt}).encode(), headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        print(error.read().decode())
        raise
    (ROOT / 'generation/idle_job.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
