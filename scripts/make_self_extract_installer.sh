#!/bin/sh
set -e

DEB_PATH=${1:-}
if [ -z "$DEB_PATH" ]; then
  echo "Usage: make_self_extract_installer.sh <path-to-deb>"
  exit 2
fi

DEB_PATH=$(cd "$(dirname "$DEB_PATH")" && pwd)/$(basename "$DEB_PATH")
OUT_DIR=$(dirname "$DEB_PATH")
OUT_FILE="$OUT_DIR/ScaleUP-Installer.run"

cat <<'SH' > "$OUT_FILE"
#!/bin/sh
set -e
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
DEB_FILE=""
if [ -f "$SCRIPT_DIR/ScaleUP-Installer.deb" ]; then
  DEB_FILE="$SCRIPT_DIR/ScaleUP-Installer.deb"
else
  DEB_FILE=$(ls "$SCRIPT_DIR"/*.deb 2>/dev/null | head -n 1)
fi
if [ -z "$DEB_FILE" ]; then
  echo "No .deb found in $SCRIPT_DIR"
  exit 2
fi

if [ -x "$SCRIPT_DIR/scaleup_installer.sh" ]; then
  exec "$SCRIPT_DIR/scaleup_installer.sh"
fi

if command -v gnome-software >/dev/null 2>&1; then
  nohup gnome-software --local-filename "$DEB_FILE" >/dev/null 2>&1 &
  exit 0
fi
if command -v software-center >/dev/null 2>&1; then
  nohup software-center "$DEB_FILE" >/dev/null 2>&1 &
  exit 0
fi
if command -v gio >/dev/null 2>&1; then
  nohup gio open "$DEB_FILE" >/dev/null 2>&1 &
  exit 0
fi
if command -v xdg-open >/dev/null 2>&1; then
  nohup xdg-open "$DEB_FILE" >/dev/null 2>&1 &
  exit 0
fi

echo "Could not open Software Install. Run: sudo apt install '$DEB_FILE'"
exit 2
SH

chmod +x "$OUT_FILE"
