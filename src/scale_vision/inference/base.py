from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from scale_vision.types import InferenceResult


class InferenceBackend(ABC):
    @abstractmethod
    def load(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def predict(self, frame) -> InferenceResult:
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError


class InferenceLoadError(RuntimeError):
    pass


class InferenceRuntimeError(RuntimeError):
    pass
