#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! "$HERE/.venv/bin/python" -c 'import PySide6' >/dev/null 2>&1; then
  echo 'PySide6 尚未安裝完成，請查看 body/install.log。' >&2
  exit 1
fi
# XWayland permits explicit side-by-side placement (native Wayland ignores move).
AUTH=$(find "/run/user/$(id -u)" -maxdepth 1 -name '.mutter-Xwaylandauth.*' -print -quit 2>/dev/null)
if [ -n "$AUTH" ] && [ -S /tmp/.X11-unix/X0 ]; then
  export DISPLAY=:0 XAUTHORITY="$AUTH" QT_QPA_PLATFORM=xcb
  export LD_LIBRARY_PATH="$HERE/xcb-libs/root/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"
fi
exec "$HERE/.venv/bin/python" "$HERE/player.py" "$@"
