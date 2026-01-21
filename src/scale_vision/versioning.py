from __future__ import annotations

import hashlib
from importlib import metadata
from pathlib import Path
from typing import Optional, Tuple


_README_CANDIDATES = [
    "README.md",
    "/opt/scale-vision/README.md",
    "/usr/local/share/scale-vision/README.md",
]


def _find_readme() -> Optional[Path]:
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        candidate = parent / "README.md"
        if candidate.exists():
            return candidate
    for seed in _README_CANDIDATES[1:]:
        candidate = Path(seed)
        if candidate.exists():
            return candidate
    return None


def _collect_seed_files() -> list[Path]:
    files: list[Path] = []
    readme = _find_readme()
    if readme is not None:
        files.append(readme)
    pkg_root = Path(__file__).resolve().parent
    files.extend(sorted(pkg_root.rglob("*.py")))
    return files


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def base_version() -> str:
    try:
        return metadata.version("scale-vision")
    except metadata.PackageNotFoundError:
        return "0.1.0"


def build_id() -> Optional[str]:
    seed_files = _collect_seed_files()
    if not seed_files:
        return None
    digest = hashlib.sha256()
    for path in seed_files:
        digest.update(str(path).encode("utf-8"))
        digest.update(_hash_file(path).encode("utf-8"))
    build_num = int(digest.hexdigest()[:8], 16) % 10000
    return f"{build_num:04d}"


def app_version() -> Tuple[str, Optional[str]]:
    base = base_version()
    build = build_id()
    if build is None:
        return base, None
    return f"{base}.{build}", build
