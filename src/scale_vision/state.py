from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from scale_vision.config.models import AppConfig
from scale_vision.observability.health import HealthState, HealthTracker
from scale_vision.observability.metrics import Metrics
from scale_vision.types import DecisionEvent


@dataclass
class RuntimeState:
    health: HealthTracker
    metrics: Metrics
    last_decision: Optional[DecisionEvent] = None
    ingestion_status: Dict[str, Any] = field(default_factory=dict)
    config: Optional[AppConfig] = None
    inference: Optional[Any] = None
    mapper: Optional[Any] = None
    inference_lock: threading.Lock = field(default_factory=threading.Lock)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def update_last_decision(self, decision: DecisionEvent) -> None:
        with self.lock:
            self.last_decision = decision

    def update_ingestion_status(self, status: Dict[str, Any]) -> None:
        with self.lock:
            self.ingestion_status = status

    def snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "last_decision": self.last_decision,
                "ingestion_status": dict(self.ingestion_status),
            }

    def health_snapshot(self) -> HealthState:
        return self.health.snapshot()
