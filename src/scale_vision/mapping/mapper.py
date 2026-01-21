from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Dict, Optional

from scale_vision.config.models import MappingConfig


@dataclass
class MapResult:
    code: Optional[str]
    reason: str


class Mapper:
    def __init__(self, config: MappingConfig) -> None:
        self._config = config
        self._checksum = self._compute_checksum(config)
        self._alias_lookup = self._build_alias_lookup(config)

    @staticmethod
    def _compute_checksum(config: MappingConfig) -> str:
        payload = json.dumps(config.dict(), sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _build_alias_lookup(config: MappingConfig) -> Dict[str, str]:
        lookup: Dict[str, str] = {}
        for class_id, entry in config.classes.items():
            for alias in entry.aliases:
                lookup[alias] = class_id
        return lookup

    def update(self, config: MappingConfig) -> None:
        self._config = config
        self._checksum = self._compute_checksum(config)
        self._alias_lookup = self._build_alias_lookup(config)

    @property
    def checksum(self) -> str:
        return self._checksum

    def map_class(self, class_id: str) -> MapResult:
        if class_id in self._alias_lookup:
            class_id = self._alias_lookup[class_id]
        entry = self._config.classes.get(class_id)
        if entry is None:
            return MapResult(code=None, reason="MAPPING_MISSING")
        if entry.disabled:
            return MapResult(code=None, reason="MAPPING_DISABLED")
        return MapResult(code=entry.code, reason="MAPPING_OK")
