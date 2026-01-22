#!/bin/sh
set -e

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
TS=$(date +%Y%m%d_%H%M%S)
OUT=${1:-"/tmp/scaleup_bundle_${TS}.tar.gz"}
TMP=$(mktemp -d)
BUNDLE="$TMP/scaleup_bundle"

mkdir -p "$BUNDLE"

copy_if_exists() {
  src="$1"
  dest="$2"
  if [ -e "$src" ]; then
    mkdir -p "$(dirname "$dest")"
    cp -R "$src" "$dest"
  fi
}

copy_if_exists "$ROOT_DIR/pyproject.toml" "$BUNDLE/pyproject.toml"
copy_if_exists "$ROOT_DIR/src" "$BUNDLE/src"
copy_if_exists "$ROOT_DIR/scripts" "$BUNDLE/scripts"
copy_if_exists "$ROOT_DIR/systemd" "$BUNDLE/systemd"
copy_if_exists "$ROOT_DIR/desktop" "$BUNDLE/desktop"
copy_if_exists "$ROOT_DIR/samples" "$BUNDLE/samples"
copy_if_exists "$ROOT_DIR/logo" "$BUNDLE/logo"
copy_if_exists "$ROOT_DIR/assets" "$BUNDLE/assets"
copy_if_exists "$ROOT_DIR/README.md" "$BUNDLE/README.md"
copy_if_exists "$ROOT_DIR/docs" "$BUNDLE/docs"

if [ -f /etc/scale-vision/config.json ]; then
  mkdir -p "$BUNDLE/config"
  cp /etc/scale-vision/config.json "$BUNDLE/config/config.json"
fi

if [ -d /var/lib/scale-vision/models/henningheyen ]; then
  mkdir -p "$BUNDLE/models"
  cp -R /var/lib/scale-vision/models/henningheyen "$BUNDLE/models/henningheyen"
fi

if [ -f /usr/share/icons/hicolor/512x512/apps/scaleup.png ]; then
  mkdir -p "$BUNDLE/icons"
  cp /usr/share/icons/hicolor/512x512/apps/scaleup.png "$BUNDLE/icons/scaleup.png"
elif [ -f /usr/share/pixmaps/scaleup.png ]; then
  mkdir -p "$BUNDLE/icons"
  cp /usr/share/pixmaps/scaleup.png "$BUNDLE/icons/scaleup.png"
fi

tar -czf "$OUT" -C "$TMP" scaleup_bundle
rm -rf "$TMP"

echo "Bundle created: $OUT"
