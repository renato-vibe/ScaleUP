from __future__ import annotations

import json
import os
from typing import List

import numpy as np

from scale_vision.inference.base import InferenceBackend, InferenceLoadError, InferenceRuntimeError
from scale_vision.types import ClassProb, InferenceResult


class OnnxInferenceBackend(InferenceBackend):
    def __init__(
        self,
        model_path: str,
        top_k: int = 5,
        device: str = "cpu",
        labels_path: str | None = None,
    ) -> None:
        self._model_path = model_path
        self._top_k = top_k
        self._device = device
        self._labels_path = labels_path
        self._labels: List[str] = []
        self._session = None
        self._input_name = ""

    @property
    def name(self) -> str:
        return "onnx"

    def load(self) -> None:
        if not os.path.exists(self._model_path):
            raise InferenceLoadError(f"Model not found: {self._model_path}")
        if self._labels_path:
            self._labels = _load_labels(self._labels_path)
        try:
            import onnxruntime as ort
        except Exception as exc:
            raise InferenceLoadError(f"onnxruntime not available: {exc}") from exc
        providers = ["CPUExecutionProvider"]
        if self._device == "gpu":
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self._session = ort.InferenceSession(self._model_path, providers=providers)
        self._input_name = self._session.get_inputs()[0].name

    def _softmax(self, logits: np.ndarray) -> np.ndarray:
        logits = logits - np.max(logits)
        exp = np.exp(logits)
        return exp / np.sum(exp)

    def _prepare_input(self, frame: np.ndarray) -> np.ndarray:
        rgb = frame[:, :, ::-1]
        tensor = rgb.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))
        return np.expand_dims(tensor, axis=0)

    def predict(self, frame) -> InferenceResult:
        if self._session is None:
            raise InferenceRuntimeError("Session not loaded")
        try:
            input_tensor = self._prepare_input(frame.image if hasattr(frame, "image") else frame)
            outputs = self._session.run(None, {self._input_name: input_tensor})
        except Exception as exc:
            raise InferenceRuntimeError(str(exc)) from exc
        if not outputs:
            raise InferenceRuntimeError("Empty ONNX outputs")
        scores = np.array(outputs[0]).squeeze()
        if scores.ndim != 1:
            scores = scores.flatten()
        if np.any(scores < 0) or np.any(scores > 1):
            scores = self._softmax(scores)
        top_k_idx = np.argsort(scores)[::-1][: self._top_k]
        labels = self._labels
        top_k: List[ClassProb] = [
            ClassProb(class_id=labels[idx] if idx < len(labels) else str(idx), prob=float(scores[idx]))
            for idx in top_k_idx
        ]
        return InferenceResult(top_k=top_k, quality_ok=True)

    @property
    def labels(self) -> List[str]:
        return list(self._labels)


def _load_labels(path: str) -> List[str]:
    if not os.path.exists(path):
        raise InferenceLoadError(f"Labels file not found: {path}")
    if path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            return [str(item) for item in payload]
        if isinstance(payload, dict):
            try:
                items = sorted(((int(k), v) for k, v in payload.items()), key=lambda x: x[0])
            except Exception as exc:
                raise InferenceLoadError("Invalid labels JSON mapping") from exc
            return [str(v) for _, v in items]
        raise InferenceLoadError("Unsupported labels JSON format")
    with open(path, "r", encoding="utf-8") as handle:
        lines = [line.strip() for line in handle.readlines()]
    return [line for line in lines if line]
