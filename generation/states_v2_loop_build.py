"""Build matching-endpoint V2 state loops without changing live actions."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    states=sys.argv[1:] or ('listening','thinking','speaking')
    if any(state not in ('listening','thinking','speaking','sleep') for state in states):
        raise SystemExit('Unsupported state')
    for state in states:
        name=state+'_v2_reference_v1'
        source=ROOT/f'body/assets/{name}.mp4'
        target=ROOT/f'body/assets/{name}_loop.mp4'
        if not target.exists():
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(source),
                '-filter_complex','[0:v]split=2[f][b];[b]reverse[r];[f][r]concat=n=2:v=1:a=0[v]',
                '-map','[v]','-an','-c:v','libx264','-preset','fast','-crf','0','-pix_fmt','yuv420p',
                '-movflags','+faststart',str(target)],check=True)
        metadata=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames',
            '-show_entries','format=duration:stream=width,height,r_frame_rate,nb_read_frames',
            '-of','json',str(target)],text=True))
        stream=metadata['streams'][0];count=int(stream['nb_read_frames'])
        data=subprocess.check_output(['ffmpeg','-hide_banner','-loglevel','error','-i',str(target),
            '-vf',f'select=eq(n\\,0)+eq(n\\,{count-1})','-fps_mode','passthrough',
            '-pix_fmt','rgb24','-f','rawvideo','pipe:1'])
        size=stream['width']*stream['height']*3
        if len(data)!=2*size or data[:size]!=data[size:]:raise SystemExit('Endpoint mismatch: '+state)
        metadata.update({'state':state,'asset':str(target),'source':str(source),
                         'first_last_decoded_rgb_identical':True,
                         'endpoint_sha256':hashlib.sha256(data[:size]).hexdigest(),
                         'construction':'forward/reverse loop','accepted_by_user':False})
        (ROOT/f'generation/{name}_loop_metadata.json').write_text(json.dumps(metadata,indent=2))
        print(state,metadata['format']['duration'],'endpoint match',flush=True)
