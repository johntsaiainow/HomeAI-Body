"""Verify displayed RGB endpoints too: native YUV equality alone misses color-tag differences."""
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'body/assets'
def rgb(name,index):
    return subprocess.check_output(['ffmpeg','-hide_banner','-loglevel','error','-i',str(ASSETS/name),
        '-vf',f'select=eq(n\\,{index})','-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','pipe:1'])
if __name__=='__main__':
    idle=rgb('idle_v2_reference_v1_loop.mp4',0)
    checks={
        'listening_starts_at_idle':rgb('listening_v3_transition_aligned.mp4',0)==idle,
        'listening_to_thinking':rgb('listening_v3_transition_aligned.mp4',96)==rgb('thinking_v3_transition_aligned.mp4',0),
        'thinking_to_speaking':rgb('thinking_v3_transition_aligned.mp4',96)==rgb('speaking_v3_entry_aligned.mp4',0),
        'speaking_entry_to_return':rgb('speaking_v3_entry_aligned.mp4',96)==rgb('speaking_v3_return_aligned.mp4',0),
        'speaking_returns_to_idle':rgb('speaking_v3_return_aligned.mp4',96)==idle,
        'vulcan_starts_and_ends_at_idle':rgb('vulcan_salute_v4_idle_connected.mp4',0)==rgb('vulcan_salute_v4_idle_connected.mp4',241)==idle,
        'vulcan_hold_preserves_approved_rgb':rgb('vulcan_salute_v4_idle_connected.mp4',100)==rgb('vulcan_salute_full_v1.mp4',120),
        'listening_cancel_end_matches_idle':rgb('listening_v3_cancel.mp4',96)==idle,
        'thinking_cancel_matches_listening':rgb('thinking_v3_cancel.mp4',96)==rgb('listening_v3_transition_aligned.mp4',96),
    }
    print(json.dumps(checks,indent=2))
    (ROOT/'generation/state-chain-v3/rgb_endpoint_checks.json').write_text(json.dumps(checks,indent=2))
    assert all(checks.values())
