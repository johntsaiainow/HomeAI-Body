"""Build or install the original geometric robot demo; never overwrites private media."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
from assets_manifest import ROOT, paths, digest

DEMO = ROOT / 'demo'
MANIFEST = ROOT / 'config/demo-assets-manifest.json'

def frame(t=0):
    width, height = 192, 256
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            color = (15, 23, 42)
            if 45 <= x < 147 and 65 <= y < 155: color = (45, 212, 191)
            if 60 <= x < 132 and 163 <= y < 224: color = (56, 189, 248)
            if 34 <= x < 52 and 171 <= y < 215 or 140 <= x < 158 and 171 <= y < 215: color = (45, 212, 191)
            if 92 <= x < 100 and 43 <= y < 65: color = (148, 163, 184)
            if (x-96)**2 + (y-39)**2 < 49: color = (251, 191, 36)
            if 72 <= x < 84 and 94 <= y < 110 or 108 <= x < 120 and 94 <= y < 110:
                color = (15, 23, 42) if t != 7 or y > 101 else (45, 212, 191)
            if 77 <= x < 115 and 132 <= y < 137: color = (15, 23, 42)
            pixels.extend(color)
    return f'P6\n{width} {height}\n255\n'.encode() + pixels

def build():
    # ffmpeg handles encoding only; the illustration is drawn entirely above.
    for suffix in ('.png', '.webp', '.mp4'):
        target = DEMO / ('robot' + suffix)
        target.parent.mkdir(parents=True, exist_ok=True)
        command = ['ffmpeg', '-v', 'error', '-y', '-f', 'image2pipe', '-vcodec', 'ppm', '-r', '12', '-i', 'pipe:0']
        if suffix == '.mp4':
            command += ['-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart']
            data = b''.join(frame(t) for t in range(24))
        else:
            command += ['-frames:v', '1']
            data = frame()
        subprocess.run(command + [str(target)], input=data, check=True)
    rows=[]
    for relative in paths():
        source = DEMO / ('robot' + Path(relative).suffix)
        rows.append({'path': relative, 'bytes': source.stat().st_size, 'sha256': digest(source)})
    MANIFEST.write_text(json.dumps({'format':1,'purpose':'Original geometric robot demo; see demo/README.md','files':rows}, indent=2)+'\n')
    print('Built shareable robot demo and manifest')

def install():
    entries=json.loads(MANIFEST.read_text())['files']
    # Validate the entire copy plan before changing any destination.
    for row in entries:
        source=DEMO / ('robot' + Path(row['path']).suffix)
        target=ROOT / row['path']
        if digest(source) != row['sha256']: raise SystemExit('Demo source checksum mismatch')
        if target.is_symlink() or target.exists() and (not target.is_file() or digest(target) != row['sha256']):
            raise SystemExit('Refusing to replace existing media: '+row['path'])
        if any(p.is_symlink() for p in target.parents if p != ROOT and ROOT in p.parents):
            raise SystemExit('Refusing symlinked destination: '+row['path'])
    for row in entries:
        target=ROOT / row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            with target.open('xb') as out:
                out.write((DEMO / ('robot'+target.suffix)).read_bytes())
    print('Installed robot demo. All states share the same placeholder animation.')

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true', help='Regenerate bundled demo with ffmpeg')
    args=parser.parse_args()
    build() if args.build else install()
