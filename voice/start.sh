#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export HOMEAI_VOICE_DIR="${HOMEAI_VOICE_DIR:-$HERE/.venv}"
export HOMEAI_VOICE_PYTHON="${HOMEAI_VOICE_PYTHON:-$HOMEAI_VOICE_DIR/bin/python}"
export HOMEAI_VOICE_SCRIPT="$HERE/agent.py"
if /usr/bin/python3 -B - <<'PY'
import os
from pathlib import Path
scripts = {os.fsencode(os.environ['HOMEAI_VOICE_SCRIPT']),
           os.fsencode(str(Path(os.environ['HOMEAI_VOICE_DIR']) / 'aion.py')),
           os.fsencode(str(Path(os.environ['HOMEAI_VOICE_DIR']) / 'offline_voice_agent.py'))}
for p in Path('/proc').iterdir():
    if not p.name.isdigit():
        continue
    try:
        if p.stat().st_uid == os.getuid() and scripts.intersection((p/'cmdline').read_bytes().split(b'\0')):
            raise SystemExit(0)
    except OSError:
        pass
raise SystemExit(1)
PY
then
  echo '已有語音程式執行，請先確認並手動停止，避免搶用麥克風。' >&2
  exit 1
fi
# Use the configured interpreter; this launcher never installs packages.
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$HERE/../body:$HERE/..${PYTHONPATH:+:$PYTHONPATH}"
export PATH="$(dirname -- "$HOMEAI_VOICE_PYTHON"):$HOME/.local/npm/bin:$PATH"
cd "$HERE"
exec "$HOMEAI_VOICE_PYTHON" -B "$HERE/agent.py"
