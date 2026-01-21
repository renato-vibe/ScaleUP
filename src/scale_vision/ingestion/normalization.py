from __future__ import annotations

from typing import Tuple

import cv2
import numpy as np


def normalize_frame(frame: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
    width, height = size
    if frame is None:
        raise ValueError("Frame is None")
    resized = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    return resized
