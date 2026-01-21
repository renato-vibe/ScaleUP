from __future__ import annotations

from typing import Optional

import numpy as np

from scale_vision.ingestion.base import IngestionBackend


class RtspIngestionBackend(IngestionBackend):
    def __init__(self) -> None:
        self._opened = False

    @property
    def name(self) -> str:
        return "rtsp"

    def open(self) -> bool:
        self._opened = True
        return False

    def read(self) -> tuple[bool, Optional[np.ndarray]]:
        return False, None

    def close(self) -> None:
        self._opened = False
