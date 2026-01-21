from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class MetricsSnapshot:
    gauges: Dict[str, float]
    counters: Dict[str, int]


class Metrics:
    def __init__(self) -> None:
        self._gauges: Dict[str, float] = {}
        self._counters: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._start_ts = time.time()

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def inc_counter(self, name: str, inc: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + inc

    def snapshot(self) -> MetricsSnapshot:
        with self._lock:
            return MetricsSnapshot(gauges=dict(self._gauges), counters=dict(self._counters))

    def render_prometheus(self) -> str:
        snapshot = self.snapshot()
        from scale_vision.versioning import app_version

        version, build = app_version()
        lines = ["# scale_vision metrics"]
        uptime = time.time() - self._start_ts
        build_label = build if build else "unknown"
        lines.append(f'scale_vision_build_info{{version="{version}",build_id="{build_label}"}} 1')
        lines.append(f"scale_vision_uptime_seconds {uptime:.3f}")
        for key, value in snapshot.gauges.items():
            lines.append(f"scale_vision_{key} {value}")
        for key, value in snapshot.counters.items():
            lines.append(f"scale_vision_{key}_total {value}")
        return "\n".join(lines) + "\n"
