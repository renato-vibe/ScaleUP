from __future__ import annotations

from scale_vision.output.base import OutputBackend
from scale_vision.types import OutputCommand


class HidOutputStub(OutputBackend):
    def __init__(self, logger) -> None:
        self._logger = logger

    @property
    def name(self) -> str:
        return "hid"

    def start(self) -> None:
        return None

    def send(self, command: OutputCommand) -> None:
        self._logger.info(
            "hid_stub_emit",
            extra={"extra": {"request_id": command.request_id, "code": command.code}},
        )

    def stop(self) -> None:
        return None
