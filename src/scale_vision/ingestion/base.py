from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from scale_vision.ingestion.buffer import FrameBuffer
from scale_vision.ingestion.normalization import normalize_frame
from scale_vision.observability.health import HealthTracker
from scale_vision.observability.metrics import Metrics
from scale_vision.types import Frame


class IngestionBackend(ABC):
    @abstractmethod
    def open(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def read(self) -> tuple[bool, Optional[np.ndarray]]:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError


@dataclass
class IngestionStatus:
    source: str
    fps_in: float = 0.0
    fps_processed: float = 0.0
    drops: int = 0
    queue_ms: float = 0.0
    reconnections: int = 0
    stale_events: int = 0
    last_frame_ts: float = 0.0
    using_synthetic: bool = False
    ok: bool = True
    details: dict = field(default_factory=dict)


class IngestionRunner:
    def __init__(
        self,
        backend: IngestionBackend,
        buffer: FrameBuffer,
        width: int,
        height: int,
        fps: int,
        health: HealthTracker,
        metrics: Metrics,
        logger,
        freeze_max_ms: int = 1200,
        enable_freeze_detection: bool = True,
    ) -> None:
        self._backend = backend
        self._buffer = buffer
        self._width = width
        self._height = height
        self._fps = fps
        self._health = health
        self._metrics = metrics
        self._logger = logger
        self._freeze_max_ms = freeze_max_ms
        self._enable_freeze = enable_freeze_detection
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._status = IngestionStatus(source=backend.name)
        self._frame_id = 0
        self._last_fps_ts = time.time()
        self._frame_count = 0
        self._processed_count = 0

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._backend.close()

    def status(self) -> IngestionStatus:
        return self._status

    def _update_fps(self) -> None:
        now = time.time()
        dt = now - self._last_fps_ts
        if dt >= 1.0:
            self._status.fps_in = self._frame_count / dt
            self._status.fps_processed = self._processed_count / dt
            self._metrics.set_gauge("fps_in", self._status.fps_in)
            self._metrics.set_gauge("fps_processed", self._status.fps_processed)
            self._frame_count = 0
            self._processed_count = 0
            self._last_fps_ts = now

    def _run(self) -> None:
        while not self._stop.is_set():
            if not self._backend.open():
                self._status.ok = False
                self._health.set_degraded(True, "INGESTION_OPEN_FAILED")
                time.sleep(1.0)
                continue
            self._health.clear_reason("INGESTION_OPEN_FAILED")
            ok, frame = self._backend.read()
            if not ok or frame is None:
                self._status.ok = False
                self._health.set_degraded(True, "INGESTION_READ_FAILED")
                time.sleep(0.05)
                continue
            self._status.ok = True
            self._health.clear_reason("INGESTION_READ_FAILED")
            now = time.time()
            try:
                normalized = normalize_frame(frame, (self._width, self._height))
            except Exception as exc:
                self._logger.error("normalize_failed", extra={"extra": {"error": str(exc)}})
                self._health.set_degraded(True, "INGESTION_NORMALIZE_FAILED")
                continue
            self._health.clear_reason("INGESTION_NORMALIZE_FAILED")
            packet = Frame(
                frame_id=self._frame_id,
                timestamp=now,
                image=normalized,
                source=self._backend.name,
                meta={},
            )
            self._frame_id += 1
            self._buffer.put(packet)
            previous_ts = self._status.last_frame_ts
            self._status.last_frame_ts = now
            self._status.queue_ms = self._buffer.queue_ms()
            self._status.drops = self._buffer.drops
            if hasattr(self._backend, "reconnections"):
                self._status.reconnections = getattr(self._backend, "reconnections")
            self._metrics.set_gauge("queue_ms", self._status.queue_ms)
            self._metrics.set_gauge("drops", float(self._status.drops))
            self._frame_count += 1
            self._processed_count += 1
            self._update_fps()

            if self._enable_freeze and previous_ts:
                stale_ms = (now - previous_ts) * 1000
                if stale_ms > self._freeze_max_ms:
                    self._status.stale_events += 1
                    self._health.set_degraded(True, "INGESTION_STALE")
                else:
                    self._health.clear_reason("INGESTION_STALE")
