"""Assemble exact idle -> approved Vulcan hold -> idle, preserving candidates."""
import json
import subprocess
import numpy as np
from state_chain_v3_align import ASSETS,ROOT,SIZE,frame,decode
if __name__=='__main__':
    idle=frame('idle_v2_reference_v1_loop.mp4',0)
    salute=frame('vulcan_salute_full_v1.mp4',120)
    chunks=[]
    for name,a,b in [('vulcan_v4_raise',idle,salute),('vulcan_v4_lower',salute,idle)]:
        data=np.frombuffer(decode(ASSETS/f'{name}.mp4'),dtype=np.uint8).reshape(-1,SIZE).copy()
        first=np.frombuffer(a,dtype=np.uint8);last=np.frombuffer(b,dtype=np.uint8)
        for i in range(8):
            w=1-i/7
            data[i]=np.rint(w*first+(1-w)*data[i]).astype(np.uint8)
            data[-1-i]=np.rint(w*last+(1-w)*data[-1-i]).astype(np.uint8)
        chunks.append(data.tobytes())
    full=chunks[0]+salute*48+chunks[1]
    target=ASSETS/'vulcan_salute_v4_idle_connected.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','yuv420p',
        '-s','512x768','-r','24','-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','0',
        '-x264-params','colorprim=bt709:transfer=iec61966-2-1:colormatrix=bt709:fullrange=off',
        '-movflags','+faststart',str(target)],input=full,check=True)
    actual=decode(target)
    assert actual[:SIZE]==actual[-SIZE:]==idle
    assert actual[97*SIZE:145*SIZE]==salute*48
    (ROOT/'generation/vulcan_v4_review.json').write_text(json.dumps({
        'asset':str(target),'frames':len(actual)//SIZE,'duration':len(actual)/SIZE/24,
        'first_last_equal_idle_first_native_yuv':True,'approved_salute_hold_seconds':2,
        'hold_frame_source':'vulcan_salute_full_v1.mp4 frame 120',
        'boundary_blend_frames':8,'visual_screening':'Raise/lower contacts viewed; fingers may vary in transit, held frame is preserved approved pose.',
        'user_accepted':False},indent=2))
    print(target,'idle endpoints and 2s approved hold PASS')
