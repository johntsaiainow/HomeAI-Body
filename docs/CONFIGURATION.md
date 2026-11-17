# Runtime configuration

Python entry points share `homeai_config.py`. Export overrides in your terminal before starting the application. No `.env` file is loaded automatically. Relative paths resolve against the process working directory; use absolute paths for overrides.

| Variable | Default | Purpose |
|---|---|---|
| `HOMEAI_COMFY_DIR` | `~/ComfyUI` | ComfyUI installation, generation input/output |
| `HOMEAI_VOICE_DIR` | `<checkout>/voice/.venv` | Voice environment directory |
| `HOMEAI_VOICE_PYTHON` | `<voice directory>/bin/python` | Interpreter for voice and camera helpers |
| `HOMEAI_VOICE_MODELS` | `<checkout>/models/voice` | Vosk and Piper model files |
| `HOMEAI_MUSIC_DIR` | `~/Music` | Voice music lookup and lyric download boundary |
| `HOMEAI_CAMERA_SCRIPT` | `~/.agents/skills/camera-vision/vision.py` | External camera client; not supplied here |
| `HOMEAI_YOLO_MODEL` | `<checkout>/models/yolov8n.pt` | Local object detection weights |
| `HOMEAI_FACE_NAME` | `使用者` | Display label for the single enrolled face |
| `HOMEAI_COMFY_REF` | none | Required upstream tag/commit when installing ComfyUI from scratch |

Example for an existing private installation (replace paths with your own):

```bash
export HOMEAI_VOICE_DIR="$HOME/existing-voice-env"
export HOMEAI_VOICE_MODELS="$HOME/existing-voice-env/models"
export HOMEAI_COMFY_DIR="$HOME/ComfyUI"
export HOMEAI_FACE_NAME='使用者'
bash voice/start.sh
```

These settings do not install optional dependencies, camera tooling or models. ASR and Taigi subprocesses still use their dedicated checkout-local environments. Shared camera socket names and Linux desktop assumptions remain prototype interfaces.

Face enrollment now uses `private/face/profile.npy`. Existing `john.npy` files are not loaded, renamed or deleted automatically. To preserve an existing enrollment, privately back it up and rename it to `profile.npy` while face tasks are stopped, or enroll again. A display label is not proof of identity.
