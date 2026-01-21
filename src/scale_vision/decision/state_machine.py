from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from scale_vision.config.models import DecisionConfig
from scale_vision.decision.voting import weighted_vote
from scale_vision.types import ClassProb, DecisionEvent, InferenceResult


@dataclass
class Observation:
    timestamp: float
    class_id: str
    prob: float


@dataclass
class DecisionState:
    state: str = "IDLE"
    observations: List[Observation] = field(default_factory=list)
    locked_class: Optional[str] = None
    last_emit_ts: float = 0.0


class DecisionEngine:
    def __init__(self, config: DecisionConfig) -> None:
        self._config = config
        self._state = DecisionState()

    @property
    def state(self) -> DecisionState:
        return self._state

    def _reset(self) -> None:
        self._state = DecisionState()

    def _trim_window(self, now: float) -> None:
        window_s = self._config.window_ms / 1000.0
        self._state.observations = [
            obs for obs in self._state.observations if now - obs.timestamp <= window_s
        ]

    def _stable_frames(self, class_id: str) -> int:
        return sum(1 for obs in self._state.observations if obs.class_id == class_id)

    def process(
        self,
        inference: InferenceResult,
        ingestion_ok: bool,
        quality_ok: bool,
        frame_id: int,
        timestamp: Optional[float] = None,
    ) -> DecisionEvent:
        now = timestamp or time.time()
        request_id = f"{int(now * 1000)}-{frame_id}"

        if not ingestion_ok:
            self._reset()
            return DecisionEvent(
                request_id=request_id,
                timestamp=now,
                state=self._state.state,
                emitted=False,
                reason_code="INGESTION_DEGRADED",
            )

        if not quality_ok:
            self._reset()
            return DecisionEvent(
                request_id=request_id,
                timestamp=now,
                state=self._state.state,
                emitted=False,
                reason_code="QUALITY_GATE",
            )

        if not inference.top_k:
            self._reset()
            return DecisionEvent(
                request_id=request_id,
                timestamp=now,
                state=self._state.state,
                emitted=False,
                reason_code="NO_PREDICTION",
            )

        top1 = inference.top_k[0]
        top2 = inference.top_k[1] if len(inference.top_k) > 1 else ClassProb("", 0.0)

        if self._state.state == "IDLE":
            self._state.state = "OBSERVING"
            self._state.observations.clear()

        if self._state.state == "OBSERVING":
            self._state.observations.append(
                Observation(timestamp=now, class_id=top1.class_id, prob=top1.prob)
            )
            self._trim_window(now)
            top_class, top_prob, margin = weighted_vote(
                [ClassProb(obs.class_id, obs.prob) for obs in self._state.observations]
            )
            stable = self._stable_frames(top_class)
            if top_prob >= self._config.min_confidence and margin >= self._config.min_margin:
                if stable >= self._config.require_stable_frames:
                    self._state.state = "COOLDOWN"
                    self._state.locked_class = top_class
                    self._state.last_emit_ts = now
                    return DecisionEvent(
                        request_id=request_id,
                        timestamp=now,
                        state="LOCKED",
                        emitted=True,
                        reason_code="EMIT",
                        class_id=top_class,
                        confidence=top_prob,
                        margin=margin,
                    )
            window_age = now - self._state.observations[0].timestamp
            if window_age > self._config.window_ms / 1000.0:
                self._reset()
                return DecisionEvent(
                    request_id=request_id,
                    timestamp=now,
                    state=self._state.state,
                    emitted=False,
                    reason_code="WINDOW_EXPIRED",
                    class_id=top_class,
                    confidence=top_prob,
                    margin=margin,
                )
            return DecisionEvent(
                request_id=request_id,
                timestamp=now,
                state="OBSERVING",
                emitted=False,
                reason_code="OBSERVING",
                class_id=top_class,
                confidence=top_prob,
                margin=margin,
            )

        if self._state.state == "COOLDOWN":
            cooldown_s = self._config.cooldown_ms / 1000.0
            elapsed = now - self._state.last_emit_ts
            scene_change = top1.class_id != (self._state.locked_class or "")
            low_conf = top1.prob < self._config.scene_change_threshold
            if elapsed >= cooldown_s and (scene_change or low_conf):
                self._reset()
                return DecisionEvent(
                    request_id=request_id,
                    timestamp=now,
                    state=self._state.state,
                    emitted=False,
                    reason_code="COOLDOWN_COMPLETE",
                )
            return DecisionEvent(
                request_id=request_id,
                timestamp=now,
                state="COOLDOWN",
                emitted=False,
                reason_code="COOLDOWN",
            )

        self._reset()
        return DecisionEvent(
            request_id=request_id,
            timestamp=now,
            state=self._state.state,
            emitted=False,
            reason_code="RESET",
        )
