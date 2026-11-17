"""Watch this installation's workers and generate one sample, never play it."""
import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parent


def status(stage,**extra):
    temporary=ROOT/'experiment-status.json.tmp'
    temporary.write_text(json.dumps({'stage':stage,'updated_at':time.time(),**extra},indent=2))
    temporary.replace(ROOT/'experiment-status.json')


def alive(pid,expected):
    try:return expected.encode() in (Path('/proc')/str(pid)/'cmdline').read_bytes()
    except OSError:return False


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--install-pid',required=True,type=int)
    parser.add_argument('--download-pid',required=True,type=int)
    args=parser.parse_args()
    started=time.monotonic()
    while True:
        dependencies=(ROOT/'DEPENDENCIES_READY').is_file()
        assets=(ROOT/'ASSETS_VERIFIED').is_file()
        if dependencies and assets:break
        if not dependencies and not alive(args.install_pid,'tts-taigi/install.sh'):
            status('failed',reason='Dependency installation exited without success; inspect install.log');return 1
        if not assets and not alive(args.download_pid,'tts-taigi/download_assets.py'):
            status('failed',reason='Asset download exited without verification; inspect download.log');return 1
        if time.monotonic()-started>24*3600:
            status('waiting_timeout',reason='Assets may still be downloading; check logs before retrying');return 1
        status('installing',dependencies_ready=dependencies,assets_verified=assets)
        time.sleep(15)
    status('generating_sample',device='cpu')
    with (ROOT/'sample.log').open('a') as log:
        try:
            result=subprocess.run([str(ROOT/'.venv/bin/python'),'-u',str(ROOT/'synthesize.py')],
                                  cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
        except subprocess.TimeoutExpired:
            status('failed',reason='Sample generation exceeded 30 minutes; inspect sample.log');return 1
    if result.returncode:
        status('failed',reason='Sample generation failed; inspect sample.log');return result.returncode
    status('sample_ready',sample=str(ROOT/'samples/taigi_first.wav'),accepted_by_user=False)
    return 0


if __name__=='__main__':raise SystemExit(main())
