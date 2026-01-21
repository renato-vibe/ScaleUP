from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from scale_vision.types import ClassProb


def weighted_vote(items: List[ClassProb]) -> Tuple[str, float, float]:
    if not items:
        return "", 0.0, 0.0
    scores: Dict[str, float] = defaultdict(float)
    for item in items:
        scores[item.class_id] += item.prob
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top1_class, top1_score = ranked[0]
    top2_score = ranked[1][1] if len(ranked) > 1 else 0.0
    total = sum(scores.values()) or 1.0
    top1_prob = top1_score / total
    margin = (top1_score - top2_score) / total
    return top1_class, top1_prob, margin
