from __future__ import annotations

import os
from typing import List, Optional

import cv2
import numpy as np

from scale_vision.inference.base import InferenceBackend, InferenceLoadError, InferenceRuntimeError
from scale_vision.types import ClassProb, InferenceResult


class KavanPatelTFBackend(InferenceBackend):
    def __init__(
        self,
        model_dir: str,
        labels_path: Optional[str] = None,
        top_k: int = 5,
        input_size: int = 416,
        score_threshold: float = 0.25,
        iou_threshold: float = 0.45,
        repo_dir: Optional[str] = None,
    ) -> None:
        self._model_dir = model_dir
        self._labels_path = labels_path
        self._top_k = top_k
        self._input_size = input_size
        self._score_threshold = score_threshold
        self._iou_threshold = iou_threshold
        self._repo_dir = repo_dir
        self._tf = None
        self._infer = None
        self._labels: List[str] = []

    @property
    def name(self) -> str:
        return "kavan_patel_tf"

    @property
    def labels(self) -> List[str]:
        return list(self._labels)

    def load(self) -> None:
        if not os.path.isdir(self._model_dir):
            raise InferenceLoadError(f"SavedModel directory not found: {self._model_dir}")
        try:
            import tensorflow as tf
        except Exception as exc:
            raise InferenceLoadError(f"tensorflow not available: {exc}") from exc
        self._tf = tf
        try:
            saved_model = tf.saved_model.load(self._model_dir, tags=["serve"])
            self._infer = saved_model.signatures["serving_default"]
        except Exception as exc:
            raise InferenceLoadError(f"Failed to load SavedModel: {exc}") from exc

        labels_path = self._resolve_labels_path()
        if labels_path:
            self._labels = _load_labels(labels_path)

    def _resolve_labels_path(self) -> Optional[str]:
        if self._labels_path and os.path.exists(self._labels_path):
            return self._labels_path
        if self._repo_dir:
            candidate = os.path.join(self._repo_dir, "data", "classes", "custom.names")
            if os.path.exists(candidate):
                return candidate
        return None

    def _prepare_input(self, frame: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self._input_size, self._input_size), interpolation=cv2.INTER_AREA)
        normalized = resized.astype(np.float32) / 255.0
        return np.expand_dims(normalized, axis=0)

    def predict(self, frame) -> InferenceResult:
        if self._infer is None or self._tf is None:
            raise InferenceRuntimeError("TensorFlow model not loaded")
        image = frame.image if hasattr(frame, "image") else frame
        if image is None:
            raise InferenceRuntimeError("Frame image is empty")
        try:
            input_batch = self._prepare_input(image)
            batch_tensor = self._tf.constant(input_batch)
            pred_bbox = self._infer(batch_tensor)
            boxes = None
            pred_conf = None
            for _, value in pred_bbox.items():
                boxes = value[:, :, 0:4]
                pred_conf = value[:, :, 4:]
            if boxes is None or pred_conf is None:
                raise InferenceRuntimeError("Model outputs are empty")

            nms = self._tf.image.combined_non_max_suppression(
                boxes=self._tf.reshape(boxes, (self._tf.shape(boxes)[0], -1, 1, 4)),
                scores=self._tf.reshape(pred_conf, (self._tf.shape(pred_conf)[0], -1, self._tf.shape(pred_conf)[-1])),
                max_output_size_per_class=50,
                max_total_size=50,
                iou_threshold=self._iou_threshold,
                score_threshold=self._score_threshold,
            )
            scores = nms[1].numpy()[0]
            classes = nms[2].numpy()[0].astype(int)
            valid = int(nms[3].numpy()[0])
        except Exception as exc:
            raise InferenceRuntimeError(str(exc)) from exc

        score_accum: dict[int, float] = {}
        for i in range(valid):
            class_id = classes[i]
            score = float(scores[i])
            if class_id < 0:
                continue
            score_accum[class_id] = max(score_accum.get(class_id, 0.0), score)

        if not score_accum:
            return InferenceResult(top_k=[], quality_ok=True, aux={"detections": valid})

        ranked = sorted(score_accum.items(), key=lambda item: item[1], reverse=True)[: self._top_k]
        labels = self._labels
        top_k = [
            ClassProb(class_id=labels[idx] if idx < len(labels) else str(idx), prob=prob)
            for idx, prob in ranked
        ]
        return InferenceResult(top_k=top_k, quality_ok=True, aux={"detections": valid})


def _load_labels(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as handle:
        return [line.strip() for line in handle.readlines() if line.strip()]
