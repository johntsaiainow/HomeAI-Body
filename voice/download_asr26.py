"""Pinned official ASR snapshot, resumable downloads with size/LFS SHA256 validation."""
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.request

REPO = 'MediaTek-Research/Breeze-ASR-26'
REVISION = '7b992682e7f5ceedd0a41ebec240f01ba469d19e'
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'models/Breeze-ASR-26'


def valid(path, item):
    if not path.is_file() or path.stat().st_size != item['size']:
        return False
    expected = item.get('lfs', {}).get('sha256')
    if expected:
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            while chunk := stream.read(8 * 1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest() == expected
    return True


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    with (DEST / '.download.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = DEST / 'download-manifest.json'
        if not manifest.exists():
            with urllib.request.urlopen(f'https://huggingface.co/api/models/{REPO}/revision/{REVISION}?blobs=true', timeout=60) as response:
                data = json.load(response)
            files = [item for item in data['siblings']
                     if item['rfilename'] not in ('.gitattributes', 'training_args.bin')]
            manifest.write_text(json.dumps({'repo': REPO, 'revision': REVISION, 'files':files}, indent=2))
        data = json.loads(manifest.read_text())
        for item in data['files']:
            name = item['rfilename']
            path = DEST / name
            if valid(path, item):
                print(f'Validated existing: {name}', flush=True)
                continue
            if path.exists():
                raise RuntimeError(f'Existing file failed validation: {path}; refusing to overwrite')
            partial = path.with_name(path.name + '.part')
            url = f'https://huggingface.co/{REPO}/resolve/{REVISION}/{name}'
            print(f'Downloading {name} ({item["size"]} bytes)', flush=True)
            subprocess.run(['curl', '--http1.1', '-L', '--fail', '--retry', '100',
                            '--retry-all-errors', '--retry-delay', '10',
                            '--connect-timeout', '30', '-C', '-', url, '-o', str(partial)], check=True)
            print(f'Verifying {name}', flush=True)
            if not valid(partial, item):
                raise RuntimeError(f'Validation failed: {partial}; retained for inspection')
            partial.rename(path)
            print(f'Validated: {name}', flush=True)
        (DEST / 'DOWNLOAD_COMPLETE').write_text(REVISION + '\n')
        print('ASR26_DOWNLOAD_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
