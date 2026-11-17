#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$ROOT/models/face"
VOICE_PYTHON="${HOMEAI_VOICE_PYTHON:-${HOMEAI_VOICE_DIR:-$ROOT/voice/.venv}/bin/python}"
mkdir -p "$DIR"
fetch() {
  local name="$1" url="$2"
  if [ ! -f "$DIR/$name.onnx" ]; then
    curl -L --fail --retry 30 --retry-all-errors --retry-delay 5 -C - "$url" -o "$DIR/$name.onnx.part"
    "$VOICE_PYTHON" -B - "$DIR/$name.onnx.part" <<'PY'
import sys, cv2
cv2.dnn.readNetFromONNX(sys.argv[1])
PY
    mv "$DIR/$name.onnx.part" "$DIR/$name.onnx"
  fi
}
fetch yunet https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
fetch sface https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
echo FACE_MODELS_READY
