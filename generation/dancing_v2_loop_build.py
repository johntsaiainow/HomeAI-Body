"""Build a reversible dance loop and verify decoded first/last frames match."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'body/assets/dancing_v2_dynamic.mp4'
TARGET=ROOT/'body/assets/dancing_v2_dynamic_loop.mp4'
if __name__=='__main__':
    if TARGET.exists():raise SystemExit('Loop exists: verify/reuse instead of overwriting')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(SOURCE),
        '-filter_complex','[0:v]split=2[f][b];[b]reverse[r];[f][r]concat=n=2:v=1:a=0[v]',
        '-map','[v]','-an','-c:v','libx264','-preset','fast','-crf','0','-pix_fmt','yuv420p',
        '-movflags','+faststart',str(TARGET)],check=True)
    metadata=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames',
        '-show_entries','format=duration:stream=width,height,r_frame_rate,nb_read_frames,profile',
        '-of','json',str(TARGET)],text=True))
    stream=metadata['streams'][0];count=int(stream['nb_read_frames'])
    data=subprocess.check_output(['ffmpeg','-hide_banner','-loglevel','error','-i',str(TARGET),
        '-vf',f'select=eq(n\\,0)+eq(n\\,{count-1})','-fps_mode','passthrough',
        '-pix_fmt','rgb24','-f','rawvideo','pipe:1'])
    size=stream['width']*stream['height']*3
    if len(data)!=size*2 or data[:size]!=data[size:]:
        raise SystemExit('First/last decoded frames differ: do not activate')
    metadata.update({'asset':str(TARGET),'source':str(SOURCE),
        'construction':'forward plus reversed source; no motion interpolation or speed change',
        'first_last_decoded_rgb_identical':True,
        'endpoint_sha256':hashlib.sha256(data[:size]).hexdigest(),'accepted_by_user':False})
    contact=ROOT/'generation/dancing_v2_dynamic_loop_contact.jpg'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(TARGET),
        '-vf','fps=1/2,scale=160:240,tile=4x3','-frames:v','1',str(contact)],check=True)
    (ROOT/'generation/dancing_v2_dynamic_loop_metadata.json').write_text(json.dumps(metadata,indent=2))
    print(json.dumps(metadata,indent=2))
