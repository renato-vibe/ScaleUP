from __future__ import annotations

import time
from typing import Optional

import serial

from scale_vision.config.models import SerialConfig
from scale_vision.output.base import OutputBackend
from scale_vision.types import OutputCommand


class SerialOutputBackend(OutputBackend):
    def __init__(self, config: SerialConfig, logger) -> None:
        self._config = config
        self._logger = logger
        self._serial: Optional[serial.Serial] = None
        self._last_connect = 0.0

    @property
    def name(self) -> str:
        return "serial"

    def start(self) -> None:
        self._connect()

    def _connect(self) -> None:
        now = time.time()
        if self._serial and self._serial.is_open:
            return
        if now - self._last_connect < self._config.reconnect_ms / 1000.0:
            return
        self._last_connect = now
        parity = {
            "none": serial.PARITY_NONE,
            "even": serial.PARITY_EVEN,
            "odd": serial.PARITY_ODD,
        }.get(self._config.parity.lower(), serial.PARITY_NONE)
        try:
            self._serial = serial.Serial(
                self._config.device,
                baudrate=self._config.baudrate,
                parity=parity,
                stopbits=self._config.stopbits,
                timeout=1,
            )
        except Exception as exc:
            self._logger.error("serial_connect_failed", extra={"extra": {"error": str(exc)}})
            self._serial = None

    def send(self, command: OutputCommand) -> None:
        if self._serial is None or not self._serial.is_open:
            self._connect()
        if self._serial is None or not self._serial.is_open:
            raise RuntimeError("Serial not connected")
        payload = f"{command.code}{command.terminator}".encode("ascii", errors="ignore")
        self._serial.write(payload)
        self._serial.flush()

    def stop(self) -> None:
        if self._serial is not None:
            self._serial.close()
        self._serial = None
