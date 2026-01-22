#!/bin/sh
set -e
MODEL_DIR=/var/lib/scale-vision/models/henningheyen
FOLDER_URL="https://drive.google.com/drive/folders/1I4mtQK11C3p41pO9raR0trgPVj0eQ2yb"
mkdir -p "$MODEL_DIR"
GDOWN_BIN=/opt/scale-vision/venv/bin/gdown
if [ ! -x "$GDOWN_BIN" ]; then
  echo "gdown not found in venv. Install with: /opt/scale-vision/venv/bin/pip install gdown"
  exit 2
fi

"$GDOWN_BIN" --folder "$FOLDER_URL" -O "$MODEL_DIR"

echo "Downloaded files in $MODEL_DIR"
ls -la "$MODEL_DIR"
