#!/bin/bash
# Dedicated CPU-only experiment. Never installs in stage one or ComfyUI.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")"
UV="$PWD/tools/bin/uv"
PY="$PWD/.venv/bin/python"
export UV_CACHE_DIR="$PWD/.uv-cache"
"$UV" pip install --python "$PY" 'torch==2.8.0+cpu' 'torchaudio==2.8.0+cpu' 'torchvision==0.23.0+cpu' --index-url https://download.pytorch.org/whl/cpu
"$UV" pip install --python "$PY" numpy==1.26.4 setuptools==78.1.0 wheel Cython
"$UV" pip install --python "$PY" --no-build-isolation-package pyworld -r requirements-local.txt
"$PY" -m compileall -q source
"$PY" -c 'import torch,torchaudio,transformers,onnxruntime,soundfile; assert not torch.cuda.is_available(); print("CPU dependencies ready",torch.__version__)'
touch DEPENDENCIES_READY
echo TAIGI_DEPENDENCIES_READY
