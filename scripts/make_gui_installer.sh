#!/bin/sh
set -e

DEB_PATH=${1:-}
if [ -z "$DEB_PATH" ]; then
  echo "Usage: make_gui_installer.sh <path-to-deb>"
  exit 2
fi

DEB_PATH=$(cd "$(dirname "$DEB_PATH")" && pwd)/$(basename "$DEB_PATH")
OUT_DIR=$(dirname "$DEB_PATH")
ICON_SRC="$(cd "$(dirname "$0")/.." && pwd)/logo/logo.png"
if [ ! -f "$ICON_SRC" ]; then
  ICON_SRC="$(cd "$(dirname "$0")/.." && pwd)/assets/scaleup.png"
fi

cat <<'SH' > "$OUT_DIR/scaleup_installer.sh"
#!/bin/sh
set -e
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
DEB_FILE=$(ls "$SCRIPT_DIR"/*.deb 2>/dev/null | head -n 1)
if [ -z "$DEB_FILE" ]; then
  echo "No .deb found in $SCRIPT_DIR"
  exit 2
fi

if [ -f "$SCRIPT_DIR/scaleup.png" ]; then
  mkdir -p "$HOME/.local/share/icons"
  cp "$SCRIPT_DIR/scaleup.png" "$HOME/.local/share/icons/scaleup.png"
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

chmod +x "$OUT_DIR/scaleup_installer.sh"

cat <<'EOF_DESKTOP' > "$OUT_DIR/ScaleUP-Installer.desktop"
[Desktop Entry]
Name=ScaleUP Installer
Comment=Install ScaleUP on this system
Exec=sh -c 'DIR=$(dirname "%k"); "$DIR/ScaleUP-Installer.run" || "$DIR/scaleup_installer.sh"'
Icon=scaleup
Type=Application
Terminal=false
Categories=Utility;
EOF_DESKTOP

if [ -f "$ICON_SRC" ]; then
  cp "$ICON_SRC" "$OUT_DIR/scaleup.png"
fi

chmod 0755 "$OUT_DIR/ScaleUP-Installer.desktop"
