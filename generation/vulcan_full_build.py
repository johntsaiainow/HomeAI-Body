"""Build a continuous raise/hold/lower candidate from the generated lowering clip."""
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'body/assets/vulcan_salute_lower_v1_candidate.mp4'
TARGET=ROOT/'body/assets/vulcan_salute_full_v1.mp4'
CONTACT=ROOT/'generation/vulcan_full_v1_contact.jpg'

if __name__=='__main__':
    if TARGET.exists():raise SystemExit('Existing full clip must be reused/reviewed, not overwritten')
    graph=('[0:v]split=3[a][b][c];'
           '[a]reverse,setpts=PTS-STARTPTS[up];'
           '[b]trim=end_frame=1,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=2,trim=duration=2[hold];'
           '[c]setpts=PTS-STARTPTS[down];'
           '[up][hold][down]concat=n=3:v=1:a=0[out]')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(SOURCE),
                    '-filter_complex',graph,'-map','[out]','-an','-c:v','libx264','-preset','fast',
                    '-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(TARGET)],check=True)
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(TARGET),
                    '-vf','fps=1,scale=160:240,tile=4x3','-frames:v','1',str(CONTACT)],check=True)
    metadata=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries',
        'format=duration:stream=width,height,r_frame_rate','-of','json',str(TARGET)],text=True))
    metadata.update({'asset':str(TARGET),'source':str(SOURCE),
        'construction':'reverse lowering clip + 2s held first frame + original lowering clip',
        'accepted_by_user':False,'contact_sheet':str(CONTACT)})
    (ROOT/'generation/vulcan_full_v1_metadata.json').write_text(json.dumps(metadata,indent=2))
    print(json.dumps(metadata,indent=2))
