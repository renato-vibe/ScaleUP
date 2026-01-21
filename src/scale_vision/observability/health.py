from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class HealthState:
    ready: bool = True
    degraded: bool = False
    reasons: List[str] = field(default_factory=list)
    details: Dict[str, str] = field(default_factory=dict)


class HealthTracker:
    def __init__(self) -> None:
        self._state = HealthState()
        self._lock = threading.Lock()

    def set_ready(self, ready: bool) -> None:
        with self._lock:
            self._state.ready = ready

    def set_degraded(self, degraded: bool, reason: str | None = None) -> None:
        with self._lock:
            self._state.degraded = degraded
            if reason and reason not in self._state.reasons:
                self._state.reasons.append(reason)

    def clear_reason(self, reason: str) -> None:
        with self._lock:
            if reason in self._state.reasons:
                self._state.reasons.remove(reason)
            if not self._state.reasons:
                self._state.degraded = False

    def set_detail(self, key: str, value: str) -> None:
        with self._lock:
            self._state.details[key] = value

    def snapshot(self) -> HealthState:
        with self._lock:
            return HealthState(
                ready=self._state.ready,
                degraded=self._state.degraded,
                reasons=list(self._state.reasons),
                details=dict(self._state.details),
            )
