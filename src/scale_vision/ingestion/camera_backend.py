from __future__ import annotations

import time
from typing import Optional

import cv2
import numpy as np

from scale_vision.config.models import CameraConfig
from scale_vision.ingestion.base import IngestionBackend


class CameraIngestionBackend(IngestionBackend):
    def __init__(self, config: CameraConfig, target_fps: int) -> None:
        self._config = config
        self._target_fps = target_fps
        self._cap: Optional[cv2.VideoCapture] = None
        self._opened = False
        self._next_reconnect_ts = 0.0
        self.reconnections = 0

    @property
    def name(self) -> str:
        return "camera"

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        if self._config.backend == "gstreamer" and self._config.gstreamer_pipeline:
            return cv2.VideoCapture(self._config.gstreamer_pipeline, cv2.CAP_GSTREAMER)
        return cv2.VideoCapture(self._config.device)

    def open(self) -> bool:
        if self._opened and self._cap is not None and self._cap.isOpened():
            return True
        now = time.time()
        if self._config.reconnect.enabled and now < self._next_reconnect_ts:
            return False
        self._cap = self._open_capture()
        if self._cap is None or not self._cap.isOpened():
            if self._config.reconnect.enabled:
                backoff = min(self._config.reconnect.max_backoff_ms, self._config.reconnect.backoff_ms)
                self._next_reconnect_ts = now + backoff / 1000
            return False
        if self._target_fps:
            self._cap.set(cv2.CAP_PROP_FPS, float(self._target_fps))
        self._opened = True
        return True

    def read(self) -> tuple[bool, Optional[np.ndarray]]:
        if not self._opened and not self.open():
            return False, None
        if self._cap is None:
            return False, None
        ok, frame = self._cap.read()
        if not ok:
            self.close()
            if self._config.reconnect.enabled:
                self.reconnections += 1
                backoff = min(
                    self._config.reconnect.max_backoff_ms,
                    self._config.reconnect.backoff_ms * max(1, self.reconnections),
                )
                self._next_reconnect_ts = time.time() + backoff / 1000
            return False, None
        return True, frame

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
        self._cap = None
        self._opened = False
