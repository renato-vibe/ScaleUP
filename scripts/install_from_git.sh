#!/bin/sh
set -e

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo bash scripts/install_from_git.sh"
  exit 2
fi

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)

if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  apt-get install -y python3 python3-venv python3-pip
fi

systemctl stop scale-vision.service || true

if ! id -u scalevision >/dev/null 2>&1; then
  useradd --system --home /var/lib/scale-vision --shell /usr/sbin/nologin scalevision
fi
usermod -a -G video scalevision || true
usermod -a -G dialout scalevision || true

APP_DIR=/opt/scale-vision/app
VENV_DIR=/opt/scale-vision/venv
CONFIG_DIR=/etc/scale-vision
DATA_DIR=/var/lib/scale-vision
LOG_DIR=/var/log/scale-vision

mkdir -p /opt/scale-vision "$CONFIG_DIR" "$DATA_DIR/models/external" "$DATA_DIR/samples" "$LOG_DIR" \
  /etc/systemd/system /usr/local/share/scale-vision /usr/share/applications /usr/local/bin

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR"
cp "$ROOT_DIR/pyproject.toml" "$APP_DIR/pyproject.toml"
cp -R "$ROOT_DIR/src" "$APP_DIR/src"

cat <<'SH' > /usr/local/bin/scale-vision
#!/bin/sh
exec /opt/scale-vision/venv/bin/scale-vision "$@"
SH
chmod +x /usr/local/bin/scale-vision

cat <<'SH' > /usr/local/bin/scaleup-ui
#!/bin/sh
exec /opt/scale-vision/venv/bin/scale-vision --config /etc/scale-vision/config.json ui "$@"
SH
chmod +x /usr/local/bin/scaleup-ui

if [ ! -f "$CONFIG_DIR/config.json" ]; then
  python3 - <<PY
import json
from pathlib import Path

with open("$ROOT_DIR/samples/sample_config_test.json", "r", encoding="utf-8") as handle:
    data = json.load(handle)
data["ingestion"]["file"]["path"] = "/var/lib/scale-vision/samples/sample.ppm"
Path("$CONFIG_DIR").mkdir(parents=True, exist_ok=True)
with open("$CONFIG_DIR/config.json", "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
PY
fi
chown scalevision:scalevision "$CONFIG_DIR/config.json" || true
chmod 664 "$CONFIG_DIR/config.json" || true

if [ -d /etc/sudoers.d ]; then
  cat <<'SUDO' > /etc/sudoers.d/scale-vision
scalevision ALL=NOPASSWD: /bin/systemctl restart scale-vision.service
SUDO
  chmod 440 /etc/sudoers.d/scale-vision
fi

if [ -f "$ROOT_DIR/systemd/scale-vision.service" ]; then
  cp "$ROOT_DIR/systemd/scale-vision.service" /etc/systemd/system/scale-vision.service
fi
if [ -f "$ROOT_DIR/samples/sample.ppm" ]; then
  cp "$ROOT_DIR/samples/sample.ppm" "$DATA_DIR/samples/sample.ppm"
fi
if [ -f "$ROOT_DIR/README.md" ]; then
  cp "$ROOT_DIR/README.md" /usr/local/share/scale-vision/README.md
fi
if [ -f "$ROOT_DIR/desktop/scaleup.desktop" ]; then
  cp "$ROOT_DIR/desktop/scaleup.desktop" /usr/share/applications/scaleup.desktop
fi

ICON_SRC="$ROOT_DIR/logo/logo.png"
ALT_ICON_SRC="$ROOT_DIR/assets/scaleup.png"
if [ -f "$ICON_SRC" ]; then
  mkdir -p /usr/share/icons/hicolor/512x512/apps
  cp "$ICON_SRC" /usr/share/icons/hicolor/512x512/apps/scaleup.png
elif [ -f "$ALT_ICON_SRC" ]; then
  mkdir -p /usr/share/icons/hicolor/512x512/apps
  cp "$ALT_ICON_SRC" /usr/share/icons/hicolor/512x512/apps/scaleup.png
fi

chown -R scalevision:scalevision "$DATA_DIR" "$LOG_DIR"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install --no-cache-dir --no-compile "$APP_DIR"

systemctl daemon-reload
systemctl enable --now scale-vision.service || true

python3 - <<PY
import json
try:
    with open("$CONFIG_DIR/config.json", "r", encoding="utf-8") as handle:
        data = json.load(handle)
    port = data.get("http", {}).get("port", 8080)
except Exception:
    port = 8080
print(f"Install complete. Open http://127.0.0.1:{port}/ or launch ScaleUP from Apps.")
PY
