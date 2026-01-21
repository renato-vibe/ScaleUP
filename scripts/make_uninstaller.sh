#!/bin/sh
set -e

OUT_DIR=${1:-}
if [ -z "$OUT_DIR" ]; then
  echo "Usage: make_uninstaller.sh <output-dir>"
  exit 2
fi

OUT_DIR=$(cd "$OUT_DIR" && pwd)
OUT_FILE="$OUT_DIR/ScaleUP-Uninstaller.run"
ICON_SRC="$(cd "$(dirname "$0")/.." && pwd)/logo/logo.png"
if [ ! -f "$ICON_SRC" ]; then
  ICON_SRC="$(cd "$(dirname "$0")/.." && pwd)/assets/scaleup.png"
fi

cat <<'SH' > "$OUT_FILE"
#!/bin/sh
set -e

if command -v zenity >/dev/null 2>&1; then
  zenity --question --title="ScaleUP Uninstaller" \
    --text="Remove ScaleUP from this system?" --ok-label="Remove" --cancel-label="Cancel" || exit 0
  zenity --question --title="ScaleUP Uninstaller" \
    --text="Do you want to purge config and data?" --ok-label="Purge" --cancel-label="Keep" && PURGE=1 || PURGE=0
else
  PURGE=0
fi

if [ "$PURGE" -eq 1 ]; then
  CMD="apt purge -y scale-vision && rm -rf /var/lib/scale-vision /var/log/scale-vision && userdel -r scalevision 2>/dev/null || true"
else
  CMD="apt remove -y scale-vision"
fi

if command -v pkexec >/dev/null 2>&1; then
  if command -v zenity >/dev/null 2>&1; then
    (
      pkexec /bin/sh -c "$CMD" >/tmp/scaleup_uninstall.log 2>&1
    ) &
    pid=$!
    zenity --progress --pulsate --no-cancel --auto-close --title="ScaleUP Uninstaller" \
      --text="Uninstalling ScaleUP..." --window-icon="scaleup" || true
    wait $pid || true
    exit 0
  fi
  pkexec /bin/sh -c "$CMD"
  exit 0
fi

echo "Run manually: sudo $CMD"
exit 2
SH

chmod +x "$OUT_FILE"

cat <<'EOF_DESKTOP' > "$OUT_DIR/ScaleUP-Uninstaller.desktop"
[Desktop Entry]
Name=ScaleUP Uninstaller
Comment=Remove ScaleUP from this system
Exec=sh -c 'DIR=$(dirname "%k"); "$DIR/ScaleUP-Uninstaller.run"'
Icon=scaleup
Type=Application
Terminal=false
Categories=Utility;
EOF_DESKTOP

chmod 0755 "$OUT_DIR/ScaleUP-Uninstaller.desktop"

if [ -f "$ICON_SRC" ]; then
  cp "$ICON_SRC" "$OUT_DIR/scaleup.png"
fi
