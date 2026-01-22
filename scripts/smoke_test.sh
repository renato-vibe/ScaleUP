#!/bin/sh
set -e

BASE=${1:-http://127.0.0.1:8081}

json_check() {
  python3 -c 'import json,sys; json.load(sys.stdin); print("ok")'
}

fetch_json() {
  url="$1"
  curl -s "$url" | json_check
}

echo "[1/6] /health"
fetch_json "$BASE/health"

echo "[2/6] /ui/status"
fetch_json "$BASE/ui/status"

echo "[3/6] /ui/mapping"
fetch_json "$BASE/ui/mapping"

echo "[4/6] /ui/config"
fetch_json "$BASE/ui/config"

echo "[5/6] /ui/config/raw"
fetch_json "$BASE/ui/config/raw"

echo "[6/6] /ui/camera/devices"
DEVICES=$(curl -s "$BASE/ui/camera/devices" | python3 -c 'import json,sys; obj=json.load(sys.stdin); print("\n".join([d.get("path","") for d in obj.get("devices",[])]))')
if [ -n "$DEVICES" ]; then
  DEVICE=$(echo "$DEVICES" | head -n 1)
  echo "Testing camera frame: $DEVICE"
  if ! curl -s "$BASE/ui/camera/frame?device=$DEVICE" -o /tmp/scaleup_smoke_frame.jpg; then
    echo "WARN: camera frame failed"
  else
    echo "Camera frame OK"
  fi
else
  echo "No cameras detected."
fi

echo "Smoke test completed."
