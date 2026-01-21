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
cp "$DEB_PATH" "$OUT_FILE"
chmod +x "$OUT_FILE"
