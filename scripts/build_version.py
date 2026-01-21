#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
content = (root / "pyproject.toml").read_text(encoding="utf-8").splitlines()
version = None
in_project = False
for line in content:
    stripped = line.strip()
    if stripped == "[project]":
        in_project = True
        continue
    if in_project and stripped.startswith("[") and stripped != "[project]":
        break
    if in_project:
        match = re.match(r'version\s*=\s*"([^"]+)"', stripped)
        if match:
            version = match.group(1)
            break
if not version:
    raise SystemExit("version not found in pyproject.toml")
print(version)
