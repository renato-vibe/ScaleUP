from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class Frame:
    frame_id: int
    timestamp: float
    image: np.ndarray
    source: str
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClassProb:
    class_id: str
    prob: float


@dataclass
class InferenceResult:
    top_k: List[ClassProb]
    quality_ok: bool = True
    blur_score: float = 0.0
    glare_score: float = 0.0
    aux: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionEvent:
    request_id: str
    timestamp: float
    state: str
    emitted: bool
    reason_code: str
    class_id: Optional[str] = None
    confidence: float = 0.0
    margin: float = 0.0
    code: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OutputCommand:
    request_id: str
    code: str
    terminator: str


@dataclass
class HealthStatus:
    ready: bool
    degraded: bool
    reasons: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


TopK = List[ClassProb]
InferenceAux = Dict[str, Any]
DecisionInputs = Tuple[InferenceResult, bool, bool]
