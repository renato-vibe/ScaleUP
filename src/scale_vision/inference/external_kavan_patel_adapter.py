from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExportResult:
    success: bool
    onnx_path: Optional[str]
    reason: str
    sha256: Optional[str] = None


def _hash_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def export_existing_onnx(repo_dir: str, output_path: str) -> ExportResult:
    for root, _, files in os.walk(repo_dir):
        for name in files:
            if name.endswith(".onnx"):
                source = os.path.join(root, name)
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                shutil.copy2(source, output_path)
                return ExportResult(
                    success=True,
                    onnx_path=output_path,
                    reason="FOUND_EXISTING_ONNX",
                    sha256=_hash_file(output_path),
                )
    return ExportResult(success=False, onnx_path=None, reason="NO_ONNX_FOUND")


def export_to_onnx(repo_dir: str, output_path: str) -> ExportResult:
    if not os.path.isdir(repo_dir):
        return ExportResult(False, None, "REPO_NOT_FOUND")
    result = export_existing_onnx(repo_dir, output_path)
    if result.success:
        return result
    return ExportResult(
        success=False,
        onnx_path=None,
        reason="TODO_EXPORT_NOT_IMPLEMENTED",
    )
