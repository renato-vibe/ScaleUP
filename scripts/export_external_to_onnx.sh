#!/bin/sh
set -e
REPO_DIR=/var/lib/scale-vision/models/external/kavan_patel
OUTPUT_PATH=/var/lib/scale-vision/models/model_kavan_patel.onnx
if [ ! -d "$REPO_DIR" ]; then
  echo "REPO_NOT_FOUND"
  exit 2
fi

ONNX_PATH=$(find "$REPO_DIR" -name "*.onnx" | head -n 1)
if [ -z "$ONNX_PATH" ]; then
  echo "NO_ONNX_FOUND: TODO_EXPORT_NOT_IMPLEMENTED"
  exit 2
fi

mkdir -p "$(dirname "$OUTPUT_PATH")"
cp "$ONNX_PATH" "$OUTPUT_PATH"
echo "EXPORTED_ONNX=$OUTPUT_PATH"
