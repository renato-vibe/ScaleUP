#!/bin/sh
set -e
. .venv/bin/activate
scale-vision run --config samples/sample_config_camera.json
