"""Track hashes, not copyrighted media/model binaries. Never touches runtime services."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'config/assets-manifest.json'

def paths():
    result={'Reference.webp'}
    actions=json.loads((ROOT/'body/actions.json').read_text())
    for entry in actions.values():
        for field in ('file','hold_image','fallback_image'):
            if field in entry:result.add('body/'+entry[field])
    sys.path.insert(0,str(ROOT/'body'))
    from transition_flow import EDGES
    result.update('body/'+file for file in EDGES.values())
    return sorted(result)

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def verify():
    manifest=MANIFEST
    demo=ROOT/'config/demo-assets-manifest.json'
    reference=ROOT/'Reference.webp'
    if demo.is_file() and reference.is_file():
        rows=json.loads(demo.read_text())['files']
        expected=next(row['sha256'] for row in rows if row['path']=='Reference.webp')
        if digest(reference)==expected:
            manifest=demo
            print('INFO using shareable robot demo manifest')
    try:entries=json.loads(manifest.read_text())['files']
    except (OSError,ValueError,KeyError):
        print('Missing or invalid assets manifest');return False
    success=True
    for row in entries:
        path=ROOT/row['path']
        if not path.is_file():print('MISSING asset:',row['path']);success=False
        elif digest(path)!=row['sha256']:print('CHANGED asset:',row['path']);success=False
    if success:print(f'PASS {len(entries)} runtime assets match manifest')
    return success

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    if args.write:
        rows=[]
        for relative in paths():
            path=ROOT/relative
            if not path.is_file():raise SystemExit('Missing asset: '+relative)
            rows.append({'path':relative,'bytes':path.stat().st_size,'sha256':digest(path)})
        MANIFEST.parent.mkdir(exist_ok=True)
        MANIFEST.write_text(json.dumps({'format':1,'purpose':'Local assets inventory; binaries excluded from Git','files':rows},indent=2)+'\n')
        print('Wrote',MANIFEST)
    else:raise SystemExit(0 if verify() else 1)
