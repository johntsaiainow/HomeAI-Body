"""Vulcan raise/return transitions from idle to the previously approved salute pose."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from homeai_config import COMFY_DIR
import subprocess
from state_chain_v3_submit import submit,FRAMES
if __name__=='__main__':
    target=FRAMES/'vulcan_target.png'
    if not target.exists():
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss','5',
            '-i',str(Path(__file__).resolve().parents[1] / 'body/assets/vulcan_salute_full_v1.mp4'),
            '-frames:v','1',str(target)],check=True)
    submit([
        ('vulcan_v4_raise','idle_first','vulcan_target',
         'Slowly raise one hand into the exact Vulcan salute of the final reference. '
         'Four straight fingers form two close pairs with a clear central gap between the middle and ring fingers. '
         'Preserve the face, proportions and the exact approved final hand shape.'),
        ('vulcan_v4_lower','vulcan_target','idle_first',
         'Begin with the exact Vulcan salute of the reference, then gently lower the arm and relax '
         'into the exact neutral idle pose of the final reference, both arms naturally down.')])
