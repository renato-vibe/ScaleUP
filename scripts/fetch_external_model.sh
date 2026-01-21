#!/bin/sh
set -e
TARGET_DIR=/var/lib/scale-vision/models/external/kavan_patel
REPO_URL=https://github.com/Kavan-Patel/Fruits-And-Vegetable-Detection-for-POS-with-Deep-Learning
mkdir -p /var/lib/scale-vision/models/external
if [ -d "$TARGET_DIR/.git" ]; then
  echo "Repo already cloned at $TARGET_DIR"
  exit 0
fi

git clone "$REPO_URL" "$TARGET_DIR"
