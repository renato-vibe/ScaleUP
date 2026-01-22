# ScaleUP

Ubuntu daemon + CLI + local API for fruit/veg recognition and POS code injection.

Source of truth: `docs/architecture_v0_3.txt`.
Production install: see `docs/INSTALL_UBUNTU.md` (offline .deb + GUI installer).

## Repo layout
- `src/scale_vision/`: core app (ingestion, inference, decision, mapping, outputs, API)
- `systemd/`: service unit
- `scripts/`: dev and packaging helpers
- `docs/`: architecture + wiring + external model notes
- `samples/`: sample configs and placeholder media

## Quickstart (test mode, no camera, no model)
```sh
make venv
. .venv/bin/activate
scale-vision run --config samples/sample_config_test.json
```

Check endpoints:
```sh
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/last-decision
curl -s http://127.0.0.1:8080/ingestion/status
curl -s http://127.0.0.1:8080/metrics
```

Version marker:
- `/health` includes `version` and `build_id`, which auto-change when `README.md` changes.

Local UI (visual test console):
- Open `http://127.0.0.1:8080/` to upload images/videos or capture a camera snapshot.
- Desktop window (no browser): `scale-vision ui` (requires `pip install 'scale-vision[desktop]'`).

## Camera mode (no emission, output=test)
```sh
scale-vision run --config samples/sample_config_camera.json
```

## Serial output (production wiring)
```sh
scale-vision run --config /etc/scale-vision/config.json
```
Edit `/etc/scale-vision/config.json`:
- `output.backend=serial`
- `output.serial.device=/dev/ttyUSB0`
- `output.serial.terminator=\r\n`

## External model integration (optional)
```sh
sudo bash scripts/fetch_external_model.sh
sudo bash scripts/export_external_to_onnx.sh
scale-vision run --config samples/sample_config_external_model.json
```
If export fails, see `docs/model_integration_kavan_patel.txt` for TODOs.
If your ONNX model outputs class indices, set `inference.labels_path` to map indexes -> class names.

## Alternative model: Henning Heyen Fruits & Vegetables (YOLOv8)
Repo + weights: https://github.com/henningheyen/Fruits-And-Vegetables-Detection-Dataset

Setup:
```sh
sudo bash scripts/fetch_external_model_henningheyen.sh
sudo /opt/scale-vision/venv/bin/pip install 'scale-vision[yolo]'
sudo bash scripts/fetch_henningheyen_weights.sh
scale-vision run --config samples/sample_config_henningheyen.json
```

## systemd
```sh
sudo cp systemd/scale-vision.service /etc/systemd/system/scale-vision.service
sudo systemctl daemon-reload
sudo systemctl enable scale-vision.service
sudo systemctl start scale-vision.service
sudo systemctl status scale-vision.service
```
Auto-start on reboot works when the service is enabled.

## Build and install .deb
Online installer (small .deb, downloads dependencies on install):
```sh
bash scripts/build_deb.sh
sudo dpkg -i dist/scale-vision_0.1.0_all/scale-vision_0.1.0_all.deb
```
This path requires network access on the Ubuntu server.

Offline installer (large .deb, all dependencies included):
```sh
DEB_ARCH=amd64 TARGET_PLATFORM=manylinux2014_x86_64 PYTHON_VERSION=310 bash scripts/build_deb_offline.sh
sudo dpkg -i dist/scale-vision_0.1.0_amd64_offline/scale-vision_0.1.0_amd64_offline.deb
```
The offline build works from macOS/Linux, but you must set the correct target architecture:
- `DEB_ARCH=amd64`, `TARGET_PLATFORM=manylinux2014_x86_64` for x86_64 servers
- `DEB_ARCH=arm64`, `TARGET_PLATFORM=manylinux2014_aarch64` for Jetson/ARM64

Faster offline install (prebuilt venv):
```sh
BUILD_PREBUILT_VENV=1 DEB_ARCH=amd64 TARGET_PLATFORM=manylinux2014_x86_64 PYTHON_VERSION=310 bash scripts/build_deb_offline.sh
```
This must run on Ubuntu (same arch as the target) and produces a larger .deb, but install time is much faster.

Desktop shortcut (optional):
- The `.deb` installs a ScaleUP desktop entry in `/usr/share/applications/scaleup.desktop`.
- Place the logo file at `logo/logo.png` before building to include the icon.

GUI installer (recommended):
- After building, open `ejecutable/ScaleUP-Installer.desktop` or run `ejecutable/ScaleUP-Installer.run`.
- The installer uses Software Install when available (and falls back to a CLI hint).

Uninstaller:
- After install, the uninstaller is available at `/opt/scale-vision/uninstall/ScaleUP-Uninstaller.run`.

## install-check
```sh
scale-vision install-check --config /etc/scale-vision/config.json
```

## Wiring and POS integration
See `docs/wiring_and_pos_integration.txt` for the 3-link diagram and preflight checklist.

## Troubleshooting
- If `/health` returns 503, inspect `/var/log/scale-vision/events.jsonl`.
- If `/health` returns 404, verify the service is running and no other app is using port 8080.
- Use the kill switch file to block output: `sudo touch /etc/scale-vision/disable_output`.
- If using serial output, ensure the user is in the `dialout` group.
