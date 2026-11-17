"""Download pinned, checksum-verified Taigi research assets; no model execution."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parent
MODEL=ROOT/'model'
MANIFEST=json.loads((ROOT/'source/assets_manifest.json').read_text())


def digest(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def download(item):
    repo,revision,name,expected,target=item
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and digest(target)==expected:
        print('Verified existing:',name,flush=True);return
    temporary=target.with_name(target.name+'.part')
    url=f'https://huggingface.co/{repo}/resolve/{revision}/{name}'
    print('Downloading:',name,flush=True)
    subprocess.run(['curl','--http1.1','--fail','--location','--retry','20','--retry-all-errors','--retry-delay','4',
        '--connect-timeout','30','--speed-limit','1024','--speed-time','120',
        '--silent','--show-error','--continue-at','-','--output',str(temporary),url],check=True)
    if digest(temporary)!=expected:raise ValueError('Checksum mismatch: '+name)
    os.replace(temporary,target)
    print('Verified:',name,'bytes',target.stat().st_size,flush=True)


def main():
    items=[(MANIFEST['upstream_repo'],MANIFEST['upstream_revision'],name,expected,MODEL/name)
           for name,expected in MANIFEST['upstream_files'].items()]
    items.append((MANIFEST['merged_repo'],MANIFEST['merged_revision'],'merged_llm.safetensors',
        MANIFEST['merged_llm_sha256'],MODEL/'merged_llm.safetensors'))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(download,items))
    (ROOT/'ASSETS_VERIFIED').write_text(json.dumps({'verified_at':time.time(),'manifest':MANIFEST},indent=2))
    print('ALL_ASSETS_VERIFIED',flush=True)


if __name__=='__main__':main()
