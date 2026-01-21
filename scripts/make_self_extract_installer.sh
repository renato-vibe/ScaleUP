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
ICON_SRC="$(cd "$(dirname "$0")/.." && pwd)/logo/logo.png"
if [ ! -f "$ICON_SRC" ]; then
  ICON_SRC="$(cd "$(dirname "$0")/.." && pwd)/assets/scaleup.png"
fi

cat <<'SH' > "$OUT_FILE"
#!/bin/sh
set -e

self="$0"
cache_dir="$HOME/.cache/scaleup_installer"
mkdir -p "$cache_dir"
icon_path="$cache_dir/scaleup.png"

if [ ! -f "$icon_path" ]; then
  start=$(awk '/^__ICON_PAYLOAD__$/ {print NR+1; exit 0; }' "$self")
  end=$(awk '/^__DEB_PAYLOAD__$/ {print NR-1; exit 0; }' "$self")
  if [ -n "$start" ] && [ -n "$end" ] && [ "$end" -ge "$start" ]; then
    sed -n "${start},${end}p" "$self" | base64 -d > "$icon_path" || true
  fi
fi

if command -v gio >/dev/null 2>&1; then
  gio set "$self" metadata::custom-icon "file://$icon_path" >/dev/null 2>&1 || true
  gio set "$self" metadata::trusted true >/dev/null 2>&1 || true
fi

payload_line=$(awk '/^__DEB_PAYLOAD__$/ {print NR+1; exit 0; }' "$self")
if [ -z "$payload_line" ]; then
  echo "Payload not found"
  exit 2
fi

deb_path="$cache_dir/scaleup_installer.deb"
tail -n "+$payload_line" "$self" > "$deb_path"

if command -v gnome-software >/dev/null 2>&1; then
  nohup gnome-software --local-filename "$deb_path" >/dev/null 2>&1 &
  exit 0
fi
if command -v software-center >/dev/null 2>&1; then
  nohup software-center "$deb_path" >/dev/null 2>&1 &
  exit 0
fi
if command -v gio >/dev/null 2>&1; then
  nohup gio open "$deb_path" >/dev/null 2>&1 &
  exit 0
fi
if command -v pkexec >/dev/null 2>&1; then
  if command -v zenity >/dev/null 2>&1; then
    (
      pkexec /bin/sh -c "apt install -y '$deb_path'" >/tmp/scaleup_install.log 2>&1
    ) &
    pid=$!
    zenity --progress --pulsate --no-cancel --auto-close --title="ScaleUP Installer" \
      --text="Installing ScaleUP. Please wait..." --window-icon="$icon_path" || true
    wait $pid || true
    exit 0
  fi
  pkexec /bin/sh -c "apt install -y '$deb_path'"
  exit 0
fi

echo "Could not launch installer GUI. Run: sudo apt install '$deb_path'"
exit 2

__DEB_PAYLOAD__
SH

if [ -f "$ICON_SRC" ]; then
  echo "__ICON_PAYLOAD__" >> "$OUT_FILE"
  base64 < "$ICON_SRC" >> "$OUT_FILE"
  echo "__DEB_PAYLOAD__" >> "$OUT_FILE"
else
  echo "__ICON_PAYLOAD__" >> "$OUT_FILE"
  echo "__DEB_PAYLOAD__" >> "$OUT_FILE"
fi

cat "$DEB_PATH" >> "$OUT_FILE"
chmod +x "$OUT_FILE"
