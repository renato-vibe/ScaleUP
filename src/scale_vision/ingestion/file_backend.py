from __future__ import annotations

import os
import time
from typing import Optional

import cv2
import numpy as np

from scale_vision.config.models import FileConfig
from scale_vision.ingestion.base import IngestionBackend


class FileIngestionBackend(IngestionBackend):
    def __init__(self, config: FileConfig, target_fps: int) -> None:
        self._config = config
        self._target_fps = target_fps
        self._cap: Optional[cv2.VideoCapture] = None
        self._image: Optional[np.ndarray] = None
        self._synthetic = False
        self._last_frame_ts = 0.0
        self._opened = False
        self._video_fps = 0.0

    @property
    def name(self) -> str:
        return "file"

    @property
    def using_synthetic(self) -> bool:
        return self._synthetic

    def open(self) -> bool:
        if self._opened:
            return True
        path = self._config.path
        if not os.path.exists(path):
            if not self._config.allow_missing:
                return False
            self._synthetic = True
            self._image = np.zeros((480, 640, 3), dtype=np.uint8)
            self._opened = True
            return True
        self._synthetic = False
        image = cv2.imread(path)
        if image is not None:
            self._image = image
            self._opened = True
            return True
        self._cap = cv2.VideoCapture(path)
        if not self._cap.isOpened():
            return False
        if self._config.start_ms:
            self._cap.set(cv2.CAP_PROP_POS_MSEC, self._config.start_ms)
        self._video_fps = self._cap.get(cv2.CAP_PROP_FPS) or 0.0
        self._opened = True
        return True

    def _sleep_for_realtime(self) -> None:
        if self._config.replay_mode != "realtime":
            return
        fps = self._video_fps or self._target_fps
        if fps <= 0:
            return
        interval = 1.0 / fps
        now = time.time()
        if self._last_frame_ts:
            elapsed = now - self._last_frame_ts
            if elapsed < interval:
                time.sleep(interval - elapsed)
        self._last_frame_ts = time.time()

    def read(self) -> tuple[bool, Optional[np.ndarray]]:
        if not self._opened and not self.open():
            return False, None
        if self._image is not None:
            self._sleep_for_realtime()
            return True, self._image.copy()
        if self._cap is None:
            return False, None
        self._sleep_for_realtime()
        ok, frame = self._cap.read()
        if ok:
            if self._config.duration_ms:
                pos = self._cap.get(cv2.CAP_PROP_POS_MSEC)
                if pos >= self._config.start_ms + self._config.duration_ms:
                    ok = False
            if ok:
                return True, frame
        if self._config.loop:
            self.close()
            self._opened = False
            return self.read()
        return False, None

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
        self._cap = None
        self._opened = False
