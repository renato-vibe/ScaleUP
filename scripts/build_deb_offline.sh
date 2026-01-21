#!/bin/sh
set -e

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
VERSION=$(python3 "$ROOT_DIR/scripts/build_version.py")
DEB_ARCH=${DEB_ARCH:-amd64}
TARGET_PLATFORM=${TARGET_PLATFORM:-manylinux2014_x86_64}
PYTHON_VERSION=${PYTHON_VERSION:-310}
PYTHON_ABI=${PYTHON_ABI:-cp${PYTHON_VERSION}}

BUILD_DIR="$ROOT_DIR/dist/scale-vision_${VERSION}_${DEB_ARCH}_offline"
PKG_ROOT="$BUILD_DIR/pkgroot"
DEBIAN_DIR="$PKG_ROOT/DEBIAN"
APP_DIR="$PKG_ROOT/opt/scale-vision/app"
WHEELS_DIR="$PKG_ROOT/opt/scale-vision/wheels"
UNINSTALL_DIR="$PKG_ROOT/opt/scale-vision/uninstall"

rm -rf "$BUILD_DIR"
mkdir -p "$DEBIAN_DIR"

mkdir -p "$PKG_ROOT/usr/local/bin" "$PKG_ROOT/opt/scale-vision" \
  "$PKG_ROOT/etc/scale-vision" "$PKG_ROOT/var/lib/scale-vision/models" \
  "$PKG_ROOT/var/lib/scale-vision/models/external" "$PKG_ROOT/var/lib/scale-vision/samples" \
  "$PKG_ROOT/var/log/scale-vision" "$PKG_ROOT/etc/systemd/system" \
  "$PKG_ROOT/usr/local/share/scale-vision" "$PKG_ROOT/usr/share/applications"

mkdir -p "$APP_DIR" "$WHEELS_DIR"
mkdir -p "$UNINSTALL_DIR"
cp "$ROOT_DIR/pyproject.toml" "$APP_DIR/pyproject.toml"
cp -R "$ROOT_DIR/src" "$APP_DIR/src"

python3 -m pip wheel --no-deps -w "$WHEELS_DIR" "$ROOT_DIR"

DEPS_FILE=$(mktemp)
python3 "$ROOT_DIR/scripts/extract_runtime_deps.py" > "$DEPS_FILE"
python3 -m pip download --only-binary=:all: \
  --platform "$TARGET_PLATFORM" \
  --implementation cp \
  --python-version "$PYTHON_VERSION" \
  --abi "$PYTHON_ABI" \
  -d "$WHEELS_DIR" \
  -r "$DEPS_FILE"
rm -f "$DEPS_FILE"

if [ "${BUILD_PREBUILT_VENV:-0}" = "1" ]; then
  if [ "$(uname -s)" != "Linux" ]; then
    echo "BUILD_PREBUILT_VENV requires Linux. Skipping prebuilt venv."
  else
    python3 -m venv "$PKG_ROOT/opt/scale-vision/venv"
    "$PKG_ROOT/opt/scale-vision/venv/bin/pip" install --upgrade pip
    "$PKG_ROOT/opt/scale-vision/venv/bin/pip" install --no-index --find-links "$WHEELS_DIR" --no-compile scale-vision
  fi
fi

cat <<'SH' > "$PKG_ROOT/usr/local/bin/scale-vision"
#!/bin/sh
exec /opt/scale-vision/venv/bin/scale-vision "$@"
SH
chmod +x "$PKG_ROOT/usr/local/bin/scale-vision"

python3 - <<PY
import json
from pathlib import Path

with open("$ROOT_DIR/samples/sample_config_test.json", "r", encoding="utf-8") as handle:
    data = json.load(handle)
data["ingestion"]["file"]["path"] = "/var/lib/scale-vision/samples/sample.ppm"
Path("$PKG_ROOT/etc/scale-vision").mkdir(parents=True, exist_ok=True)
with open("$PKG_ROOT/etc/scale-vision/config.json", "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
PY

cp "$ROOT_DIR/systemd/scale-vision.service" "$PKG_ROOT/etc/systemd/system/scale-vision.service"
cp "$ROOT_DIR/samples/sample.ppm" "$PKG_ROOT/var/lib/scale-vision/samples/sample.ppm"
cp "$ROOT_DIR/README.md" "$PKG_ROOT/usr/local/share/scale-vision/README.md"
cp "$ROOT_DIR/desktop/scaleup.desktop" "$PKG_ROOT/usr/share/applications/scaleup.desktop"

UNINSTALL_STAGE="$BUILD_DIR/uninstall"
mkdir -p "$UNINSTALL_STAGE"
bash "$ROOT_DIR/scripts/make_uninstaller.sh" "$UNINSTALL_STAGE"
cp "$UNINSTALL_STAGE/ScaleUP-Uninstaller.run" "$UNINSTALL_DIR/ScaleUP-Uninstaller.run"
chmod 0755 "$UNINSTALL_DIR/ScaleUP-Uninstaller.run"

ICON_SRC="$ROOT_DIR/logo/logo.png"
ALT_ICON_SRC="$ROOT_DIR/assets/scaleup.png"
if [ -f "$ICON_SRC" ]; then
  mkdir -p "$PKG_ROOT/usr/share/icons/hicolor/512x512/apps"
  cp "$ICON_SRC" "$PKG_ROOT/usr/share/icons/hicolor/512x512/apps/scaleup.png"
elif [ -f "$ALT_ICON_SRC" ]; then
  mkdir -p "$PKG_ROOT/usr/share/icons/hicolor/512x512/apps"
  cp "$ALT_ICON_SRC" "$PKG_ROOT/usr/share/icons/hicolor/512x512/apps/scaleup.png"
fi

cp "$ROOT_DIR/debian/control" "$DEBIAN_DIR/control"
python3 - <<PY
from pathlib import Path

path = Path("$DEBIAN_DIR/control")
lines = path.read_text(encoding="utf-8").splitlines()
updated = []
for line in lines:
    if line.startswith("Architecture:"):
        updated.append(f"Architecture: $DEB_ARCH")
    else:
        updated.append(line)
path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY

cp "$ROOT_DIR/debian/postinst" "$DEBIAN_DIR/postinst"
cp "$ROOT_DIR/debian/prerm" "$DEBIAN_DIR/prerm"
cp "$ROOT_DIR/debian/postrm" "$DEBIAN_DIR/postrm"
cp "$ROOT_DIR/debian/conffiles" "$DEBIAN_DIR/conffiles"
chmod 0755 "$DEBIAN_DIR/postinst" "$DEBIAN_DIR/prerm" "$DEBIAN_DIR/postrm"

python3 "$ROOT_DIR/scripts/build_deb_portable.py" "$PKG_ROOT" "$BUILD_DIR/scale-vision_${VERSION}_${DEB_ARCH}_offline.deb"

mkdir -p "$ROOT_DIR/ejecutable"
cp "$BUILD_DIR/scale-vision_${VERSION}_${DEB_ARCH}_offline.deb" \
  "$ROOT_DIR/ejecutable/scale-vision_${VERSION}_${DEB_ARCH}_offline.deb"
cp "$BUILD_DIR/scale-vision_${VERSION}_${DEB_ARCH}_offline.deb" \
  "$ROOT_DIR/ejecutable/ScaleUP-Installer.deb"
