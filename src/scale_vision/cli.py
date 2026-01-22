from __future__ import annotations

import argparse
import glob
import os
import sys

from scale_vision.config.loader import ConfigLoader
from scale_vision.versioning import app_version, base_version
from scale_vision.desktop_app import launch_app
from scale_vision.main import run


def install_check(config_path: str) -> int:
    issues = []
    if not os.path.exists(config_path):
        issues.append(f"config_missing:{config_path}")
        return _report(issues)
    loader = ConfigLoader(config_path)
    loaded = loader.load()
    config = loaded.config

    if config.ingestion.source == "camera":
        devices = glob.glob("/dev/video*")
        if not devices:
            issues.append("camera_device_missing")
    if config.output.backend == "serial":
        devices = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
        if not devices:
            issues.append("serial_device_missing")
    if config.inference.backend == "onnx":
        if not os.path.exists(config.inference.model_path):
            issues.append("onnx_model_missing")
        try:
            import onnxruntime  # noqa: F401
        except Exception:
            issues.append("onnxruntime_missing")

    return _report(issues)


def _report(issues) -> int:
    if not issues:
        print("install-check: OK")
        return 0
    print("install-check: FAIL")
    for issue in issues:
        print(f"- {issue}")
    return 2


def main() -> None:
    parser = argparse.ArgumentParser(prog="scale-vision")
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    parser.add_argument("--config", default="/etc/scale-vision/config.json")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run")
    sub.add_parser("install-check")
    ui_parser = sub.add_parser("ui")
    ui_parser.add_argument("--url", default="", help="Override UI URL (default from config)")

    args = parser.parse_args()
    if args.version:
        visible, build = app_version()
        build_suffix = f" (build {build})" if build else ""
        print(f"scale-vision {base_version()} -> {visible}{build_suffix}")
        return
    if args.command in (None, "run"):
        run(args.config)
        return
    if args.command == "install-check":
        sys.exit(install_check(args.config))
    if args.command == "ui":
        url = args.url or None
        sys.exit(launch_app(args.config, url))


if __name__ == "__main__":
    main()
