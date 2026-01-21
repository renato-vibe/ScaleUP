#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


def extract_dependencies(pyproject: Path) -> list[str]:
    content = pyproject.read_text(encoding="utf-8").splitlines()
    deps: list[str] = []
    in_project = False
    in_deps = False
    for line in content:
        stripped = line.strip()
        if stripped == "[project]":
            in_project = True
            continue
        if in_project and stripped.startswith("[") and stripped != "[project]":
            break
        if in_project and stripped.startswith("dependencies") and stripped.endswith("["):
            in_deps = True
            continue
        if in_deps:
            if stripped.startswith("]"):
                break
            match = re.match(r'"([^"]+)"', stripped)
            if match:
                deps.append(match.group(1))
    return deps


if __name__ == "__main__":
    deps = extract_dependencies(Path("pyproject.toml"))
    for dep in deps:
        print(dep)
