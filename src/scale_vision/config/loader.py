from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from typing import Optional, Tuple

from .models import AppConfig


@dataclass
class LoadedConfig:
    config: AppConfig
    checksum: str
    path: str
    mtime: float


class ConfigLoader:
    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._loaded: Optional[LoadedConfig] = None

    @staticmethod
    def _compute_checksum(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def load(self) -> LoadedConfig:
        with self._lock:
            with open(self._path, "r", encoding="utf-8") as handle:
                payload = handle.read()
            data = json.loads(payload)
            config = AppConfig.parse_obj(data)
            checksum = self._compute_checksum(payload)
            mtime = os.path.getmtime(self._path)
            self._loaded = LoadedConfig(config=config, checksum=checksum, path=self._path, mtime=mtime)
            return self._loaded

    def reload_if_changed(self) -> Tuple[LoadedConfig, bool]:
        with self._lock:
            if self._loaded is None:
                return self.load(), True
            mtime = os.path.getmtime(self._path)
            if mtime <= self._loaded.mtime:
                return self._loaded, False
            old_checksum = self._loaded.checksum
            loaded = self.load()
            changed = loaded.checksum != old_checksum
            return loaded, changed

    @property
    def current(self) -> Optional[LoadedConfig]:
        return self._loaded
