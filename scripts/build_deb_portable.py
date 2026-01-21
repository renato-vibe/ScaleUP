#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
from pathlib import Path


def _tar_directory(source: Path, target: Path, exclude: list[str] | None = None) -> None:
    exclude = exclude or []
    with tarfile.open(target, "w:gz", format=tarfile.GNU_FORMAT) as tar:
        for path in sorted(source.rglob("*")):
            rel = path.relative_to(source)
            if any(str(rel).startswith(pattern) for pattern in exclude):
                continue
            tar.add(path, arcname=str(rel), recursive=False)


def _write_ar(files: list[tuple[str, Path]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as handle:
        handle.write(b"!<arch>\n")
        for name, path in files:
            data = path.read_bytes()
            header = (
                f"{name}/".ljust(16)
                + f"{int(path.stat().st_mtime)}".ljust(12)
                + f"0".ljust(6)
                + f"0".ljust(6)
                + f"100644".ljust(8)
                + f"{len(data)}".ljust(10)
                + "`\n"
            )
            handle.write(header.encode("utf-8"))
            handle.write(data)
            if len(data) % 2 == 1:
                handle.write(b"\n")


def build_deb(pkgroot: Path, output: Path) -> None:
    debian_dir = pkgroot / "DEBIAN"
    if not debian_dir.exists():
        raise SystemExit("DEBIAN directory missing")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        control_tar = tmp_path / "control.tar.gz"
        data_tar = tmp_path / "data.tar.gz"
        debian_binary = tmp_path / "debian-binary"

        debian_binary.write_text("2.0\n", encoding="utf-8")
        _tar_directory(debian_dir, control_tar)
        _tar_directory(pkgroot, data_tar, exclude=["DEBIAN"])

        _write_ar(
            [
                ("debian-binary", debian_binary),
                ("control.tar.gz", control_tar),
                ("data.tar.gz", data_tar),
            ],
            output,
        )


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        raise SystemExit("Usage: build_deb_portable.py <pkgroot> <output.deb>")
    build_deb(Path(sys.argv[1]), Path(sys.argv[2]))
