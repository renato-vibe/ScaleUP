from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class NormalizeConfig(BaseModel):
    width: int = 640
    height: int = 640
    fps: int = 15


class BufferConfig(BaseModel):
    max_ms: int = 800
    drop_policy: str = "drop_oldest"
    max_frames: int = 30


class CameraReconnectConfig(BaseModel):
    enabled: bool = True
    backoff_ms: int = 1000
    max_backoff_ms: int = 10000


class FreezeDetectionConfig(BaseModel):
    enabled: bool = True
    max_stale_ms: int = 1200


class CameraConfig(BaseModel):
    device: str = "/dev/video0"
    backend: str = "opencv"
    gstreamer_pipeline: str = ""
    reconnect: CameraReconnectConfig = Field(default_factory=CameraReconnectConfig)
    freeze_detection: FreezeDetectionConfig = Field(default_factory=FreezeDetectionConfig)


class FileConfig(BaseModel):
    path: str = "/var/lib/scale-vision/samples/sample.ppm"
    replay_mode: str = "realtime"
    loop: bool = True
    start_ms: int = 0
    duration_ms: int = 0
    allow_missing: bool = True


class IngestionConfig(BaseModel):
    source: str = "file"
    normalize: NormalizeConfig = Field(default_factory=NormalizeConfig)
    buffer: BufferConfig = Field(default_factory=BufferConfig)
    camera: CameraConfig = Field(default_factory=CameraConfig)
    file: FileConfig = Field(default_factory=FileConfig)


class ExternalExportConfig(BaseModel):
    enabled: bool = True
    output_onnx_path: str = "/var/lib/scale-vision/models/model_kavan_patel.onnx"
    input_size: int = 640


class ExternalModelConfig(BaseModel):
    enabled: bool = False
    provider: str = "kavan_patel"
    repo_url: str = "https://github.com/Kavan-Patel/Fruits-And-Vegetable-Detection-for-POS-with-Deep-Learning"
    checkout: str = "main"
    install_dir: str = "/var/lib/scale-vision/models/external/kavan_patel"
    export: ExternalExportConfig = Field(default_factory=ExternalExportConfig)


class InferenceConfig(BaseModel):
    backend: str = "stub"
    model_path: str = "/var/lib/scale-vision/models/model.onnx"
    top_k: int = 5
    device: str = "cpu"
    fallback_to_stub: bool = True
    external: ExternalModelConfig = Field(default_factory=ExternalModelConfig)
    stub_classes: List[str] = Field(default_factory=list)


class DecisionConfig(BaseModel):
    window_ms: int = 800
    min_confidence: float = 0.78
    min_margin: float = 0.10
    cooldown_ms: int = 2500
    require_stable_frames: int = 8
    scene_change_threshold: float = 0.40
    block_on_ingestion_degraded: bool = True


class MappingEntry(BaseModel):
    code_type: str = "plu"
    code: str
    aliases: List[str] = Field(default_factory=list)
    disabled: bool = False


class MappingConfig(BaseModel):
    default_action: str = "block"
    classes: Dict[str, MappingEntry] = Field(default_factory=dict)


class SerialConfig(BaseModel):
    device: str = "/dev/ttyUSB0"
    baudrate: int = 9600
    parity: str = "none"
    stopbits: int = 1
    terminator: str = "\r\n"
    reconnect_ms: int = 1000


class OutputConfig(BaseModel):
    backend: str = "test"
    suffix: str = "\n"
    serial: SerialConfig = Field(default_factory=SerialConfig)


class SafetyConfig(BaseModel):
    kill_switch_file: str = "/etc/scale-vision/disable_output"


class HttpConfig(BaseModel):
    enabled: bool = True
    bind: str = "127.0.0.1"
    port: int = 8080


class LoggingConfig(BaseModel):
    level: str = "INFO"
    log_dir: str = "/var/log/scale-vision"
    json_log_file: str = "events.jsonl"


class AppConfig(BaseModel):
    mode: str = "test"
    ingestion: IngestionConfig = Field(default_factory=IngestionConfig)
    inference: InferenceConfig = Field(default_factory=InferenceConfig)
    decision: DecisionConfig = Field(default_factory=DecisionConfig)
    mapping: MappingConfig = Field(default_factory=MappingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    http: HttpConfig = Field(default_factory=HttpConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    class Config:
        extra = "forbid"
