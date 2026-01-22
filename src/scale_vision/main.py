from __future__ import annotations

import json
import os
import signal
import threading
import time
from typing import Optional

from scale_vision.api import create_app
from scale_vision.config.loader import ConfigLoader
from scale_vision.config.models import AppConfig
from scale_vision.decision.quality import quality_gate
from scale_vision.decision.state_machine import DecisionEngine
from scale_vision.inference.base import InferenceLoadError, InferenceRuntimeError
from scale_vision.inference.onnx_backend import OnnxInferenceBackend
from scale_vision.inference.kavan_patel_tf_backend import KavanPatelTFBackend
from scale_vision.inference.ultralytics_backend import UltralyticsBackend
from scale_vision.inference.stub_backend import StubInferenceBackend
from scale_vision.ingestion.base import IngestionRunner
from scale_vision.ingestion.buffer import FrameBuffer
from scale_vision.ingestion.camera_backend import CameraIngestionBackend
from scale_vision.ingestion.file_backend import FileIngestionBackend
from scale_vision.ingestion.rtsp_backend import RtspIngestionBackend
from scale_vision.mapping.mapper import Mapper
from scale_vision.observability.health import HealthTracker
from scale_vision.observability.metrics import Metrics
from scale_vision.observability.logging import setup_logging
from scale_vision.output.hid_stub import HidOutputStub
from scale_vision.output.serial_backend import SerialOutputBackend
from scale_vision.output.test_backend import TestOutputBackend
from scale_vision.state import RuntimeState
from scale_vision.types import DecisionEvent, OutputCommand
from scale_vision.versioning import app_version


def _build_ingestion(config: AppConfig):
    buffer = FrameBuffer(
        max_ms=config.ingestion.buffer.max_ms,
        max_frames=config.ingestion.buffer.max_frames,
        drop_policy=config.ingestion.buffer.drop_policy,
    )
    if config.ingestion.source == "camera":
        backend = CameraIngestionBackend(config.ingestion.camera, config.ingestion.normalize.fps)
        freeze_cfg = config.ingestion.camera.freeze_detection
    elif config.ingestion.source == "rtsp":
        backend = RtspIngestionBackend()
        freeze_cfg = config.ingestion.camera.freeze_detection
    else:
        backend = FileIngestionBackend(config.ingestion.file, config.ingestion.normalize.fps)
        freeze_cfg = config.ingestion.camera.freeze_detection
    return backend, buffer, freeze_cfg


def _build_inference(config: AppConfig):
    if config.inference.backend == "kavan_patel_tf":
        return KavanPatelTFBackend(
            model_dir=config.inference.model_path,
            labels_path=config.inference.labels_path,
            top_k=config.inference.top_k,
            repo_dir=config.inference.external.install_dir,
        )
    if config.inference.backend == "ultralytics":
        return UltralyticsBackend(
            model_path=config.inference.model_path,
            top_k=config.inference.top_k,
            device=config.inference.device,
        )
    if config.inference.backend == "onnx":
        return OnnxInferenceBackend(
            model_path=config.inference.model_path,
            top_k=config.inference.top_k,
            device=config.inference.device,
            labels_path=config.inference.labels_path,
        )
    return StubInferenceBackend(config.inference.stub_classes, config.inference.top_k)


def _build_output(config: AppConfig, logger):
    if config.output.backend == "serial":
        return SerialOutputBackend(config.output.serial, logger)
    if config.output.backend == "hid":
        return HidOutputStub(logger)
    return TestOutputBackend(logger)


def _start_api(config: AppConfig, state: RuntimeState) -> Optional[threading.Thread]:
    if not config.http.enabled:
        return None
    import uvicorn

    app = create_app(state)
    server = uvicorn.Server(
        uvicorn.Config(app, host=config.http.bind, port=config.http.port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return thread


def run(config_path: str) -> None:
    loader = ConfigLoader(config_path)
    loaded = loader.load()
    config = loaded.config
    logger = setup_logging(config.logging)
    visible, build = app_version()
    logger.info(
        "startup",
        extra={"extra": {"config_checksum": loaded.checksum, "version": visible, "build_id": build}},
    )

    health = HealthTracker()
    metrics = Metrics()
    state = RuntimeState(health=health, metrics=metrics)
    state.config = config
    state.config_path = config_path

    backend, buffer, freeze_cfg = _build_ingestion(config)
    ingestion_runner = IngestionRunner(
        backend=backend,
        buffer=buffer,
        width=config.ingestion.normalize.width,
        height=config.ingestion.normalize.height,
        fps=config.ingestion.normalize.fps,
        health=health,
        metrics=metrics,
        logger=logger,
        freeze_max_ms=freeze_cfg.max_stale_ms,
        enable_freeze_detection=freeze_cfg.enabled,
    )
    ingestion_runner.start()

    inference = _build_inference(config)
    try:
        inference.load()
    except InferenceLoadError as exc:
        health.set_degraded(True, "INFERENCE_LOAD_FAILED")
        logger.error("inference_load_failed", extra={"extra": {"error": str(exc)}})
        if config.inference.fallback_to_stub:
            inference = StubInferenceBackend(config.inference.stub_classes, config.inference.top_k)
            inference.load()
            health.clear_reason("INFERENCE_LOAD_FAILED")
    state.inference = inference

    decision_engine = DecisionEngine(config.decision)
    mapper = Mapper(config.mapping)
    state.mapper = mapper
    output_backend = _build_output(config, logger)
    output_backend.start()

    _start_api(config, state)

    stop = threading.Event()

    def handle_signal(signum, _frame):
        logger.info("shutdown_signal", extra={"extra": {"signal": signum}})
        stop.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    while not stop.is_set():
        frame = buffer.get(timeout=1.0)
        if frame is None:
            health.set_degraded(True, "INGESTION_TIMEOUT")
            continue
        health.clear_reason("INGESTION_TIMEOUT")

        status = ingestion_runner.status()
        if hasattr(backend, "using_synthetic"):
            status.using_synthetic = getattr(backend, "using_synthetic")
        status_dict = status.__dict__.copy()
        state.update_ingestion_status(status_dict)

        try:
            with state.inference_lock:
                result = inference.predict(frame)
            health.clear_reason("INFERENCE_RUNTIME_FAILED")
        except InferenceRuntimeError as exc:
            health.set_degraded(True, "INFERENCE_RUNTIME_FAILED")
            logger.error("inference_runtime_failed", extra={"extra": {"error": str(exc)}})
            if config.inference.fallback_to_stub and inference.name != "stub":
                inference = StubInferenceBackend(config.inference.stub_classes, config.inference.top_k)
                inference.load()
                health.clear_reason("INFERENCE_RUNTIME_FAILED")
                state.inference = inference
            continue

        quality_ok = quality_gate(result)
        health_state = health.snapshot()
        ingestion_degraded = any(reason.startswith("INGESTION") for reason in health_state.reasons)
        ingestion_ok = not ingestion_degraded or not config.decision.block_on_ingestion_degraded

        decision = decision_engine.process(
            inference=result,
            ingestion_ok=ingestion_ok,
            quality_ok=quality_ok,
            frame_id=frame.frame_id,
            timestamp=frame.timestamp,
        )

        if decision.emitted and decision.class_id:
            map_result = mapper.map_class(decision.class_id)
            if map_result.code is None:
                decision.emitted = False
                decision.reason_code = map_result.reason
            else:
                decision.code = map_result.code

        if decision.emitted and decision.code:
            kill_switch = config.safety.kill_switch_file
            if os.path.exists(kill_switch):
                decision.emitted = False
                decision.reason_code = "KILL_SWITCH"
            elif health_state.degraded:
                decision.emitted = False
                decision.reason_code = "HEALTH_DEGRADED"
            else:
                try:
                    output_backend.send(OutputCommand(
                        request_id=decision.request_id,
                        code=decision.code,
                        terminator=config.output.serial.terminator,
                    ))
                    health.clear_reason("OUTPUT_FAILED")
                    metrics.inc_counter("emit", 1)
                except Exception as exc:
                    health.set_degraded(True, "OUTPUT_FAILED")
                    decision.emitted = False
                    decision.reason_code = "OUTPUT_FAILED"
                    logger.error("output_failed", extra={"extra": {"error": str(exc)}})

        state.update_last_decision(decision)
        logger.info(
            "decision_event",
            extra={
                "extra": {
                    "request_id": decision.request_id,
                    "state": decision.state,
                    "emitted": decision.emitted,
                    "reason_code": decision.reason_code,
                    "class_id": decision.class_id,
                    "confidence": decision.confidence,
                    "margin": decision.margin,
                    "code": decision.code,
                    "source": frame.source,
                    "frame_id": frame.frame_id,
                }
            },
        )

        loaded, changed = loader.reload_if_changed()
        if changed:
            config = loaded.config
            mapper.update(config.mapping)
            decision_engine = DecisionEngine(config.decision)
            state.config = config
            logger.info("config_reloaded", extra={"extra": {"checksum": loaded.checksum}})

    output_backend.stop()
    ingestion_runner.stop()
    logger.info("shutdown_complete")
