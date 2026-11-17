"""Small English-specific Whisper model, verified into stage two only."""
import json
from pathlib import Path
import urllib.request
import download_asr26 as downloader

ROOT=Path(__file__).resolve().parents[1]
with urllib.request.urlopen('https://huggingface.co/api/models/openai/whisper-tiny.en?blobs=true',timeout=60) as response:
    metadata=json.load(response)
destination=ROOT/'models/whisper-tiny.en'
destination.mkdir(parents=True,exist_ok=True)
files=[item for item in metadata['siblings'] if item['rfilename']=='model.safetensors'
       or (('/' not in item['rfilename']) and item['rfilename'].endswith(('.json','.txt')))]
(destination/'download-manifest.json').write_text(json.dumps({'repo':'openai/whisper-tiny.en','revision':metadata['sha'],'files':files},indent=2))
downloader.REPO='openai/whisper-tiny.en'
downloader.REVISION=metadata['sha']
downloader.DEST=destination
downloader.main()
