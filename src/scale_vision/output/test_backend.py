from __future__ import annotations

from typing import List

from scale_vision.output.base import OutputBackend
from scale_vision.types import OutputCommand


class TestOutputBackend(OutputBackend):
    def __init__(self, logger) -> None:
        self._logger = logger
        self._sent: List[OutputCommand] = []

    @property
    def name(self) -> str:
        return "test"

    def start(self) -> None:
        return None

    def send(self, command: OutputCommand) -> None:
        self._sent.append(command)
        self._logger.info(
            "output_test_emit",
            extra={"extra": {"request_id": command.request_id, "code": command.code}},
        )

    def stop(self) -> None:
        return None

    @property
    def sent(self) -> List[OutputCommand]:
        return list(self._sent)
