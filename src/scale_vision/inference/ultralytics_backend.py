from __future__ import annotations

from typing import Dict, List, Optional

import contextlib

import numpy as np

from scale_vision.inference.base import InferenceBackend, InferenceLoadError, InferenceRuntimeError
from scale_vision.types import ClassProb, InferenceResult


class UltralyticsBackend(InferenceBackend):
    def __init__(self, model_path: str, top_k: int = 5, device: str = "cpu") -> None:
        self._model_path = model_path
        self._top_k = top_k
        self._device = device
        self._model = None
        self._names: Dict[int, str] = {}

    @property
    def name(self) -> str:
        return "ultralytics"

    @property
    def labels(self) -> List[str]:
        if not self._names:
            return []
        return [name for _, name in sorted(self._names.items(), key=lambda item: item[0])]

    def load(self) -> None:
        try:
            from ultralytics import YOLO
        except Exception as exc:
            raise InferenceLoadError(f"ultralytics not available: {exc}") from exc
        safe_ctx = contextlib.nullcontext()
        try:
            import torch
            from ultralytics.nn.tasks import DetectionModel

            default_to_weights_only = getattr(torch.serialization, "_default_to_weights_only", None)
            if callable(default_to_weights_only):
                torch.serialization._default_to_weights_only = lambda *args, **kwargs: False
            if hasattr(torch.serialization, "safe_globals"):
                safe_ctx = torch.serialization.safe_globals([DetectionModel])
        except Exception:
            safe_ctx = contextlib.nullcontext()

        try:
            with safe_ctx:
                self._model = YOLO(self._model_path)
        except Exception as exc:
            raise InferenceLoadError(f"Failed to load model: {exc}") from exc
        try:
            self._names = {int(k): str(v) for k, v in self._model.names.items()}
        except Exception:
            self._names = {}

    def predict(self, frame) -> InferenceResult:
        if self._model is None:
            raise InferenceRuntimeError("Model not loaded")
        image = frame.image if hasattr(frame, "image") else frame
        if image is None:
            raise InferenceRuntimeError("Frame image is empty")
        try:
            results = self._model.predict(
                source=image,
                device=self._device,
                verbose=False,
                conf=0.2,
                iou=0.5,
            )
            if not results:
                return InferenceResult(top_k=[], quality_ok=True)
            result = results[0]
            boxes = getattr(result, "boxes", None)
            if boxes is None or len(boxes) == 0:
                return InferenceResult(top_k=[], quality_ok=True)
            cls_ids = boxes.cls.cpu().numpy().astype(int)
            confs = boxes.conf.cpu().numpy().astype(float)
        except Exception as exc:
            raise InferenceRuntimeError(str(exc)) from exc

        score_accum: Dict[int, float] = {}
        for cls_id, conf in zip(cls_ids, confs):
            score_accum[cls_id] = max(score_accum.get(cls_id, 0.0), float(conf))

        ranked = sorted(score_accum.items(), key=lambda item: item[1], reverse=True)[: self._top_k]
        top_k = [
            ClassProb(class_id=self._names.get(idx, str(idx)), prob=prob)
            for idx, prob in ranked
        ]
        return InferenceResult(top_k=top_k, quality_ok=True, aux={"detections": len(confs)})
