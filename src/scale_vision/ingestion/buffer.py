from __future__ import annotations

import collections
import threading
import time
from typing import Deque, Optional

from scale_vision.types import Frame


class FrameBuffer:
    def __init__(self, max_ms: int, max_frames: int, drop_policy: str = "drop_oldest") -> None:
        self._queue: Deque[Frame] = collections.deque()
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._max_ms = max_ms
        self._max_frames = max_frames
        self._drop_policy = drop_policy
        self.drops = 0

    def _drop_oldest(self) -> None:
        if self._queue:
            self._queue.popleft()
            self.drops += 1

    def put(self, frame: Frame) -> None:
        with self._lock:
            now = frame.timestamp
            while self._queue and (now - self._queue[0].timestamp) * 1000 > self._max_ms:
                self._drop_oldest()
            if len(self._queue) >= self._max_frames:
                if self._drop_policy == "drop_oldest":
                    self._drop_oldest()
                else:
                    self.drops += 1
                    return
            self._queue.append(frame)
            self._not_empty.notify()

    def get(self, timeout: float | None = None) -> Optional[Frame]:
        with self._not_empty:
            if not self._queue:
                if not self._not_empty.wait(timeout=timeout):
                    return None
            if not self._queue:
                return None
            return self._queue.popleft()

    def queue_ms(self) -> float:
        with self._lock:
            if not self._queue:
                return 0.0
            now = time.time()
            return max(0.0, (now - self._queue[0].timestamp) * 1000)
