#!/bin/sh
set -e
TARGET_DIR=/var/lib/scale-vision/models/external/henningheyen
REPO_URL=https://github.com/henningheyen/Fruits-And-Vegetables-Detection-Dataset
mkdir -p /var/lib/scale-vision/models/external
if [ -d "$TARGET_DIR/.git" ]; then
  echo "Repo already cloned at $TARGET_DIR"
  exit 0
fi

git clone "$REPO_URL" "$TARGET_DIR"
