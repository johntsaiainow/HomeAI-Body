"""Read-only local readiness report. No model downloads or microphone/camera access."""
from pathlib import Path
import shutil
import subprocess
import sys
from assets_manifest import verify
ROOT=Path(__file__).resolve().parents[1]

def main():
    ok=True
    for tool in ('mpv','ffmpeg','ffprobe'):
        found=shutil.which(tool)
        print(('PASS ' if found else 'MISSING ')+tool)
        ok=ok and bool(found)
    interpreter=ROOT/'body/.venv/bin/python'
    if interpreter.is_file():
        result=subprocess.run([str(interpreter),'-B','-c','import PySide6, numpy, opencc; print("PASS desktop Python imports")'],
                              capture_output=True,text=True,timeout=30)
        if result.returncode:
            print('MISSING desktop Python packages; run installer --body --upgrade');ok=False
        else:print(result.stdout.strip())
    else:print('MISSING body/.venv; run installer --body');ok=False
    ok=verify() and ok
    # These are warnings, not a claim that a full voice installation was validated.
    print('INFO desktop-only installer; full voice/ASR/TTS/camera setup is separate.')
    print('INFO optional voice environments and camera integration require configuration; see docs/INSTALL.md.')
    print('INFO no services were started, stopped, or accessed by this check.')
    return 0 if ok else 1

if __name__=='__main__':raise SystemExit(main())
