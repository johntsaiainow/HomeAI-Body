#!/usr/bin/env bash
set -euo pipefail
COMFY_DIR="${HOMEAI_COMFY_DIR:-$HOME/ComfyUI}"
trap 'echo "Installation failed at line $LINENO"' ERR
mkdir -p "$COMFY_DIR"
cd "$COMFY_DIR"
# Set an explicit upstream tag or commit before installing.
if [ ! -f main.py ]; then
  : "${HOMEAI_COMFY_REF:?Set HOMEAI_COMFY_REF to a reviewed ComfyUI tag or commit}"
  ARCHIVE=$(mktemp)
  trap 'rm -f "$ARCHIVE"' EXIT
  curl -L --fail --retry 5 --connect-timeout 30 --max-time 3600 "https://codeload.github.com/comfyanonymous/ComfyUI/tar.gz/${HOMEAI_COMFY_REF}" -o "$ARCHIVE"
  tar -xzf "$ARCHIVE" --strip-components=1
fi
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -c 'import torch; print("PyTorch:", torch.__version__); print("CUDA available:", torch.cuda.is_available()); assert torch.cuda.is_available(), "CUDA unavailable"; print(torch.cuda.get_device_name(0))'
echo 'INSTALL_COMPLETE'
