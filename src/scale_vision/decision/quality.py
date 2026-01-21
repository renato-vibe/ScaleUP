from __future__ import annotations

from scale_vision.types import InferenceResult


def quality_gate(result: InferenceResult, blur_threshold: float = 0.5, glare_threshold: float = 0.5) -> bool:
    if not result.quality_ok:
        return False
    if result.blur_score > blur_threshold:
        return False
    if result.glare_score > glare_threshold:
        return False
    return True
