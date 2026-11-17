#!/usr/bin/env bash
set -euo pipefail
COMFY_DIR="${HOMEAI_COMFY_DIR:-$HOME/ComfyUI}"
cd "$COMFY_DIR"
exec .venv/bin/python main.py --listen 127.0.0.1 --port 8188 --lowvram "$@"
