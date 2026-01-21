#!/bin/sh
set -e

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found"
  exit 2
fi

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)

IMAGE=ubuntu:22.04

docker run --rm -t \
  -v "$ROOT_DIR":/workspace \
  -w /workspace \
  "$IMAGE" \
  bash -lc "apt-get update && apt-get install -y --no-install-recommends python3 python3-venv python3-pip && bash scripts/build_deb.sh"
