from __future__ import annotations

import random
from typing import List

from scale_vision.inference.base import InferenceBackend
from scale_vision.types import ClassProb, InferenceResult


class StubInferenceBackend(InferenceBackend):
    def __init__(self, classes: List[str], top_k: int = 5) -> None:
        self._classes = classes or ["apple_red", "banana", "orange"]
        self._top_k = min(top_k, len(self._classes))

    @property
    def name(self) -> str:
        return "stub"

    def load(self) -> None:
        return None

    def predict(self, frame) -> InferenceResult:
        frame_id = getattr(frame, "frame_id", 0)
        rng = random.Random(frame_id)
        scores = [rng.random() for _ in self._classes]
        total = sum(scores) or 1.0
        probs = [s / total for s in scores]
        ranked = sorted(
            [ClassProb(class_id=cid, prob=prob) for cid, prob in zip(self._classes, probs)],
            key=lambda item: item.prob,
            reverse=True,
        )
        top_k = ranked[: self._top_k]
        blur_score = float(rng.random()) * 0.2
        glare_score = float(rng.random()) * 0.2
        return InferenceResult(top_k=top_k, quality_ok=True, blur_score=blur_score, glare_score=glare_score)
