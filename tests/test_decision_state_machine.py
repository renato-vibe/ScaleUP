from scale_vision.config.models import DecisionConfig
from scale_vision.decision.state_machine import DecisionEngine
from scale_vision.types import ClassProb, InferenceResult


def _make_result(class_id: str, prob: float, alt_prob: float = 0.05):
    return InferenceResult(
        top_k=[ClassProb(class_id=class_id, prob=prob), ClassProb(class_id="alt", prob=alt_prob)]
    )


def test_emits_once_per_episode():
    config = DecisionConfig(window_ms=500, min_confidence=0.6, min_margin=0.1, cooldown_ms=200)
    engine = DecisionEngine(config)
    ts = 0.0
    emitted = []
    for i in range(10):
        ts += 0.05
        decision = engine.process(_make_result("apple", 0.9), True, True, i, ts)
        emitted.append(decision.emitted)
    assert any(emitted)
    assert emitted.count(True) == 1


def test_block_on_ingestion_degraded():
    config = DecisionConfig()
    engine = DecisionEngine(config)
    decision = engine.process(_make_result("apple", 0.9), False, True, 1, 1.0)
    assert decision.emitted is False
    assert decision.reason_code == "INGESTION_DEGRADED"
