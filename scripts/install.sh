#!/usr/bin/env bash
# Safe, desktop-only bootstrap. Never installs into the legacy voice environment.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
export PYTHONDONTWRITEBYTECODE=1
PYTHON="${PYTHON:-python3}"
mode=check
upgrade=false
for arg in "$@"; do
  case "$arg" in
    --check) mode=check ;;
    --body) mode=body ;;
    --upgrade) upgrade=true ;;
    -h|--help)
      printf '%s\n' 'Usage: bash scripts/install.sh [--check | --body [--upgrade]]' \
        '--check: read-only desktop readiness check (default).' \
        '--body: create private body/.venv and install desktop dependencies.' \
        '--upgrade: explicitly permit changing an existing desktop environment.' \
        'No sudo, service restart, model download, voice install or camera enrollment.'
      exit 0 ;;
    *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
  esac
done
case "$ROOT/" in
  "$HOME/aion-voice/"*) echo 'Refusing to modify stage one.' >&2; exit 1 ;;
esac
if [[ "$mode" == check ]]; then
  exec "$PYTHON" -B "$ROOT/scripts/doctor.py"
fi
command -v "$PYTHON" >/dev/null || { echo 'Python 3 is required.' >&2; exit 1; }
"$PYTHON" -c 'import sys; assert sys.version_info >= (3,10), "Python >=3.10 required"'
ENV="$ROOT/body/.venv"
if [[ -L "$ENV" ]]; then echo 'Refusing a symlinked desktop environment.' >&2; exit 1; fi
if [[ -e "$ENV" ]] && ! "$upgrade"; then
  echo 'Desktop environment already exists; left untouched. Use --check or explicitly --body --upgrade.' >&2
  exit 1
fi
if [[ ! -e "$ENV" ]]; then "$PYTHON" -m venv "$ENV"; fi
"$ENV/bin/python" -m pip install -r "$ROOT/body/requirements.txt"
# Opt-in network feature is OFF on fresh installs. Existing preferences are untouched.
if [[ ! -e "$ROOT/body/lyrics-settings.json" ]]; then
  "$PYTHON" - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
try:
    with (root/'body/lyrics-settings.json').open('x') as out:
        out.write((root/'config/examples/lyrics-settings.json').read_text())
except FileExistsError:
    pass
PY
fi
printf '\nDesktop dependencies installed. No application or hardware service was started.\n'
if ! "$PYTHON" -B "$ROOT/scripts/doctor.py"; then
  echo 'Python setup finished; supply the missing runtime assets/system dependencies listed above before launching.'
fi
