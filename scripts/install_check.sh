#!/bin/sh
set -e
CONFIG_PATH=${1:-/etc/scale-vision/config.json}
scale-vision install-check --config "$CONFIG_PATH"
