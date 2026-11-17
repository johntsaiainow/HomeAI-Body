"""Resumable official English Vosk model installation, stage two only."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile
import shutil

ROOT=Path(__file__).resolve().parents[1]/'models'
NAME='vosk-model-small-en-us-0.15'
archive=ROOT/(NAME+'.zip')
url='https://alphacephei.com/vosk/models/'+archive.name
subprocess.run(['curl','-fL','--silent','--show-error','--retry','20','--retry-all-errors',
    '--retry-delay','3','--connect-timeout','20','--speed-limit','1024','--speed-time','30',
    '-C','-','-o',str(archive),url],check=True)
temporary=ROOT/(NAME+'.extracting')
temporary.mkdir(exist_ok=True)
with zipfile.ZipFile(archive) as z:
    for item in z.infolist():
        if not (temporary/item.filename).resolve().is_relative_to(temporary.resolve()):
            raise ValueError('Unsafe archive path')
    if z.testzip():raise ValueError('Archive CRC failed')
    z.extractall(temporary)
model=temporary/NAME
for name in ['am/final.mdl','conf/model.conf','graph/HCLr.fst','graph/Gr.fst']:
    if not (model/name).is_file():raise ValueError('Incomplete model: '+name)
with archive.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
(model/'DOWNLOAD_COMPLETE').write_text(json.dumps({'source':url,'sha256':sha,'archive_crc_verified':True}))
# The digest is recorded locally; it is not an independently published checksum.
model.rename(ROOT/NAME)
shutil.rmtree(temporary)
print('ENGLISH_VOSK_READY',flush=True)
