#!/usr/bin/env bash
set -euo pipefail
COMFY_DIR="${HOMEAI_COMFY_DIR:-$HOME/ComfyUI}"
mkdir -p "$COMFY_DIR/models/text_encoders"
cd "$COMFY_DIR/models/text_encoders"
name=t5xxl_fp8_e4m3fn.safetensors
if [ -f "$name" ]; then echo 'Already downloaded'; exit 0; fi
curl --http1.1 -L --fail --retry 30 --retry-all-errors --retry-delay 10 -C - "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/$name" -o "$name.part"
"$COMFY_DIR/.venv/bin/python" - "$name.part" <<'PY'
import sys, os, json, struct
from safetensors import safe_open
p=sys.argv[1]
with open(p,'rb') as f:
    n=struct.unpack('<Q',f.read(8))[0]
    assert n < 100_000_000
    h=json.loads(f.read(n))
assert 8+n+max(v['data_offsets'][1] for k,v in h.items() if k!='__metadata__') == os.path.getsize(p)
with safe_open(p,framework='pt',device='cpu') as f:
    print('Validated tensor index:',len(list(f.keys())))
os.rename(p,p.removesuffix('.part'))
print('T5_DOWNLOAD_COMPLETE')
PY
