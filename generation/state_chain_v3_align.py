"""Align candidate endpoints to decoded source YUV frames; preserve raw LTX clips."""
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'body/assets'
SIZE=512*768*3//2

def run(args):return subprocess.check_output(['ffmpeg','-hide_banner','-loglevel','error',*args])
def frame(name,index):
    raw=run(['-i',str(ASSETS/name),'-vf',f'select=eq(n\\,{index})','-frames:v','1','-pix_fmt','yuv420p','-f','rawvideo','pipe:1'])
    assert len(raw)==SIZE
    return raw

def decode(path):return run(['-i',str(path),'-pix_fmt','yuv420p','-f','rawvideo','pipe:1'])
if __name__=='__main__':
    anchors={'idle':frame('idle_v2_reference_v1_loop.mp4',0)}
    for state in ('listening','thinking','speaking'):
        anchors[state]=frame(f'{state}_v2_reference_v1.mp4',48)
    links=[('listening_v3_transition','idle','listening'),
           ('thinking_v3_transition','listening','thinking'),
           ('speaking_v3_entry','thinking','speaking'),
           ('speaking_v3_return','speaking','idle')]
    review=[];parts=[]
    for name,start,end in links:
        data=np.frombuffer(decode(ASSETS/f'{name}.mp4'),dtype=np.uint8).reshape(-1,SIZE).copy()
        a=np.frombuffer(anchors[start],dtype=np.uint8);b=np.frombuffer(anchors[end],dtype=np.uint8)
        before=[float(np.abs(data[0].astype(float)-a).mean()),float(np.abs(data[-1].astype(float)-b).mean())]
        # Gentle eight-frame boundary blend; encoded endpoint is the exact native source frame.
        for i in range(8):
            weight=1-i/7
            data[i]=np.rint(weight*a+(1-weight)*data[i]).astype(np.uint8)
            data[-1-i]=np.rint(weight*b+(1-weight)*data[-1-i]).astype(np.uint8)
        target=ASSETS/f'{name}_aligned.mp4'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','yuv420p',
            '-s','512x768','-r','24','-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','0',
            '-x264-params','colorprim=bt709:transfer=iec61966-2-1:colormatrix=bt709:fullrange=off',
            '-movflags','+faststart',str(target)],input=data.tobytes(),check=True)
        check=decode(target)
        assert check[:SIZE]==anchors[start] and check[-SIZE:]==anchors[end]
        parts.append(target)
        review.append({'asset':str(target),'start':start,'end':end,'frames':len(data),
            'original_yuv_endpoint_mean_absolute_error':before,
            'endpoint_yuv_byte_identical':True,'boundary_blend_frames':8,
            'first_yuv_sha256':hashlib.sha256(check[:SIZE]).hexdigest(),
            'last_yuv_sha256':hashlib.sha256(check[-SIZE:]).hexdigest()})
        print(name,'exact endpoints PASS',flush=True)
    playlist=ROOT/'generation/state-chain-v3/preview_concat.txt'
    playlist.write_text(''.join(f"file '{p}'\n" for p in parts))
    preview=ASSETS/'state_chain_v3_preview.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0',
        '-i',str(playlist),'-c','copy',str(preview)],check=True)
    raw=decode(preview)
    assert raw[:SIZE]==raw[-SIZE:]==anchors['idle']
    (ROOT/'generation/state-chain-v3/alignment_review.json').write_text(json.dumps({
        'links':review,'preview':str(preview),'full_cycle_first_last_identical':True,
        'live_actions_replaced':False,'user_accepted':False,
        'note':'Generated candidates with endpoint boundary blends; no claim of frame-perfect natural motion or audio lipsync.'},indent=2))
