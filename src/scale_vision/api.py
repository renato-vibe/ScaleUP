from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from typing import Dict, List, Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import HTMLResponse

from scale_vision.config.models import AppConfig
from scale_vision.decision.quality import quality_gate
from scale_vision.decision.state_machine import DecisionEngine
from scale_vision.ingestion.normalization import normalize_frame
from scale_vision.state import RuntimeState
from scale_vision.types import Frame, InferenceResult
from scale_vision.versioning import app_version

_UI_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ScaleUP - Local Console</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #0f172a;
        --panel: #111827;
        --card: #0b1220;
        --muted: #9ca3af;
        --text: #e5e7eb;
        --accent: #22d3ee;
        --accent-2: #38bdf8;
        --danger: #f97316;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Fira Sans", "Noto Sans", sans-serif;
        background: radial-gradient(1200px 600px at 20% -10%, #1e3a8a, transparent),
                    radial-gradient(900px 500px at 120% 20%, #0f766e, transparent),
                    var(--bg);
        color: var(--text);
        min-height: 100vh;
      }
      header {
        padding: 28px 32px 12px;
        display: flex;
        justify-content: space-between;
        align-items: baseline;
      }
      header h1 {
        margin: 0;
        font-size: 28px;
        letter-spacing: 0.6px;
      }
      header span {
        color: var(--muted);
        font-size: 14px;
      }
      main {
        padding: 12px 32px 40px;
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: 16px;
      }
      .card {
        background: linear-gradient(160deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02));
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 16px;
        padding: 16px;
        backdrop-filter: blur(6px);
        min-height: 160px;
      }
      .card h2 {
        margin: 0 0 12px;
        font-size: 16px;
        color: var(--accent);
      }
      .meta {
        font-size: 12px;
        color: var(--muted);
      }
      .grid-2 {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 8px;
      }
      .badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(34, 211, 238, 0.12);
        border: 1px solid rgba(34, 211, 238, 0.35);
        color: var(--accent);
        font-size: 12px;
      }
      pre {
        margin: 0;
        font-size: 12px;
        line-height: 1.5;
        white-space: pre-wrap;
        word-break: break-word;
      }
      .controls {
        display: grid;
        gap: 12px;
      }
      .controls input[type="file"] {
        width: 100%;
        padding: 8px;
        border-radius: 10px;
        border: 1px dashed rgba(148, 163, 184, 0.4);
        background: rgba(15, 23, 42, 0.6);
        color: var(--text);
      }
      button {
        background: linear-gradient(135deg, var(--accent), var(--accent-2));
        color: #0f172a;
        font-weight: 600;
        border: none;
        border-radius: 10px;
        padding: 10px 14px;
        cursor: pointer;
      }
      button.secondary {
        background: transparent;
        color: var(--text);
        border: 1px solid rgba(148, 163, 184, 0.4);
      }
      .row {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }
      .status-pill {
        padding: 6px 10px;
        border-radius: 999px;
        font-size: 12px;
        background: rgba(148, 163, 184, 0.1);
        border: 1px solid rgba(148, 163, 184, 0.2);
      }
      .status-pill.ok { border-color: rgba(34, 211, 238, 0.6); color: var(--accent); }
      .status-pill.warn { border-color: rgba(249, 115, 22, 0.6); color: var(--danger); }
      video, canvas {
        width: 100%;
        border-radius: 12px;
        background: #0b1220;
      }
      footer {
        padding: 0 32px 32px;
        color: var(--muted);
        font-size: 12px;
      }
    </style>
  </head>
  <body>
    <header>
      <div>
        <h1>ScaleUP Local Console</h1>
        <span id="version">loading version...</span>
      </div>
      <span class="badge">Local API</span>
    </header>
    <main>
      <section class="card">
        <h2>Health</h2>
        <div class="row" id="health-badges"></div>
        <div class="meta" id="health-meta"></div>
      </section>
      <section class="card">
        <h2>Ingestion</h2>
        <pre id="ingestion"></pre>
      </section>
      <section class="card">
        <h2>Last Decision</h2>
        <pre id="decision"></pre>
      </section>
      <section class="card">
        <h2>Output + Safety</h2>
        <pre id="system"></pre>
      </section>
      <section class="card">
        <h2>Quick Test (Image or Video)</h2>
        <div class="controls">
          <input id="fileInput" type="file" accept="image/*,video/*" />
          <div class="row">
            <button id="runButton">Run Test</button>
            <button id="refreshButton" class="secondary">Refresh Status</button>
          </div>
          <pre id="predict"></pre>
        </div>
      </section>
      <section class="card">
        <h2>Camera Snapshot</h2>
        <div class="controls">
          <video id="camera" autoplay playsinline></video>
          <canvas id="canvas" style="display:none;"></canvas>
          <div class="row">
            <button id="cameraStart">Start Camera</button>
            <button id="cameraCapture" class="secondary">Capture + Test</button>
          </div>
          <pre id="cameraResult"></pre>
        </div>
      </section>
    </main>
    <footer>ScaleUP runs locally. If /health returns 404, check the service port in /etc/scale-vision/config.json.</footer>
    <script>
      const el = (id) => document.getElementById(id);
      const pretty = (obj) => JSON.stringify(obj, null, 2);

      async function fetchJson(path) {
        const res = await fetch(path);
        if (!res.ok) throw new Error(await res.text());
        return res.json();
      }

      async function refreshStatus() {
        try {
          const health = await fetchJson("/health");
          const ingestion = await fetchJson("/ingestion/status");
          const decision = await fetchJson("/last-decision");
          const system = await fetchJson("/ui/status");
          el("version").textContent = `version ${health.version} (${health.build_id})`;
          const badges = [];
          badges.push(`<span class="status-pill ${health.degraded ? "warn" : "ok"}">ready=${health.ready}</span>`);
          badges.push(`<span class="status-pill ${health.degraded ? "warn" : "ok"}">degraded=${health.degraded}</span>`);
          el("health-badges").innerHTML = badges.join("");
          el("health-meta").textContent = health.reasons && health.reasons.length ? health.reasons.join(", ") : "healthy";
          el("ingestion").textContent = pretty(ingestion);
          el("decision").textContent = pretty(decision);
          el("system").textContent = pretty(system);
        } catch (err) {
          el("health-meta").textContent = `error: ${err}`;
        }
      }

      async function runPredict(file, target) {
        try {
          const form = new FormData();
          form.append("file", file);
          const res = await fetch("/ui/predict", { method: "POST", body: form });
          const payload = await res.json();
          target.textContent = pretty(payload);
        } catch (err) {
          target.textContent = `error: ${err}`;
        }
      }

      el("runButton").addEventListener("click", () => {
        const file = el("fileInput").files[0];
        if (!file) {
          el("predict").textContent = "Please select an image or video.";
          return;
        }
        runPredict(file, el("predict"));
      });

      el("refreshButton").addEventListener("click", refreshStatus);

      let stream = null;
      el("cameraStart").addEventListener("click", async () => {
        try {
          stream = await navigator.mediaDevices.getUserMedia({ video: true });
          el("camera").srcObject = stream;
        } catch (err) {
          el("cameraResult").textContent = `camera error: ${err}`;
        }
      });

      el("cameraCapture").addEventListener("click", async () => {
        const video = el("camera");
        if (!video.srcObject) {
          el("cameraResult").textContent = "Camera not started.";
          return;
        }
        const canvas = el("canvas");
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob((blob) => {
          if (!blob) {
            el("cameraResult").textContent = "Failed to capture frame.";
            return;
          }
          const file = new File([blob], "camera.jpg", { type: "image/jpeg" });
          runPredict(file, el("cameraResult"));
        }, "image/jpeg", 0.9);
      });

      refreshStatus();
      setInterval(refreshStatus, 4000);
    </script>
  </body>
</html>
"""


def _frame_id_from_bytes(payload: bytes) -> int:
    digest = hashlib.sha256(payload).hexdigest()
    return int(digest[:8], 16)


def _map_top_k(state: RuntimeState, result: InferenceResult) -> List[Dict[str, Optional[float]]]:
    mapped: List[Dict[str, Optional[float]]] = []
    mapper = state.mapper
    for item in result.top_k:
        code = None
        reason = None
        if mapper is not None:
            map_result = mapper.map_class(item.class_id)
            code = map_result.code
            reason = map_result.reason
        mapped.append(
            {"class_id": item.class_id, "prob": item.prob, "code": code, "mapping_reason": reason}
        )
    return mapped


def _get_config(state: RuntimeState) -> AppConfig:
    return state.config or AppConfig()


def create_app(state: RuntimeState) -> FastAPI:
    app = FastAPI(title="scale-vision", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    def ui_index() -> HTMLResponse:
        return HTMLResponse(_UI_HTML)

    @app.get("/health")
    def health() -> Response:
        snapshot = state.health_snapshot()
        visible, build = app_version()
        payload = {
            "ready": snapshot.ready,
            "degraded": snapshot.degraded,
            "reasons": snapshot.reasons,
            "details": snapshot.details,
            "version": visible,
            "build_id": build,
        }
        status = 200 if snapshot.ready and not snapshot.degraded else 503
        return Response(content=json.dumps(payload), media_type="application/json", status_code=status)

    @app.get("/metrics")
    def metrics() -> Response:
        content = state.metrics.render_prometheus()
        return Response(content=content, media_type="text/plain")

    @app.get("/last-decision")
    def last_decision() -> dict:
        snapshot = state.snapshot()
        decision = snapshot["last_decision"]
        return decision.__dict__ if decision else {}

    @app.get("/ingestion/status")
    def ingestion_status() -> dict:
        snapshot = state.snapshot()
        return snapshot["ingestion_status"]

    @app.get("/ui/status")
    def ui_status() -> dict:
        config = _get_config(state)
        serial_device = config.output.serial.device
        serial_exists = os.path.exists(serial_device)
        serial_writable = os.access(serial_device, os.W_OK) if serial_exists else False
        kill_switch = config.safety.kill_switch_file
        return {
            "output_backend": config.output.backend,
            "serial_device": serial_device,
            "serial_exists": serial_exists,
            "serial_writable": serial_writable,
            "kill_switch_active": os.path.exists(kill_switch),
            "inference_backend": state.inference.name if state.inference else config.inference.backend,
            "http_bind": config.http.bind,
            "http_port": config.http.port,
        }

    @app.post("/ui/predict")
    async def ui_predict(file: UploadFile = File(...)) -> dict:
        config = _get_config(state)
        if state.inference is None:
            raise HTTPException(status_code=503, detail="Inference backend not available")
        payload = await file.read()
        if not payload:
            raise HTTPException(status_code=400, detail="Empty upload")
        filename = (file.filename or "").lower()
        content_type = (file.content_type or "").lower()
        is_video = content_type.startswith("video/") or filename.endswith((".mp4", ".avi", ".mov", ".mkv"))

        width = config.ingestion.normalize.width
        height = config.ingestion.normalize.height
        fps = max(1, config.ingestion.normalize.fps)
        frame_stride = max(1, int(round(fps / 4)))
        max_frames = 30

        decision_engine = DecisionEngine(config.decision)
        decision = None
        last_result: Optional[InferenceResult] = None
        last_quality_ok = False
        processed = 0

        if not is_video:
            image = cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise HTTPException(status_code=400, detail="Unsupported image format")
            normalized = normalize_frame(image, (width, height))
            frame_id = _frame_id_from_bytes(payload)
            frame = Frame(frame_id=frame_id, timestamp=time.time(), image=normalized, source="ui")
            with state.inference_lock:
                last_result = state.inference.predict(frame)
            last_quality_ok = quality_gate(last_result)
            decision = decision_engine.process(
                inference=last_result,
                ingestion_ok=True,
                quality_ok=last_quality_ok,
                frame_id=frame.frame_id,
                timestamp=frame.timestamp,
            )
            processed = 1
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1] or ".mp4") as handle:
                handle.write(payload)
                temp_path = handle.name
            try:
                cap = cv2.VideoCapture(temp_path)
                if not cap.isOpened():
                    raise HTTPException(status_code=400, detail="Unsupported video format")
                frame_id = 0
                while processed < max_frames:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    frame_id += 1
                    if frame_id % frame_stride != 0:
                        continue
                    normalized = normalize_frame(frame, (width, height))
                    frame_obj = Frame(
                        frame_id=frame_id,
                        timestamp=time.time(),
                        image=normalized,
                        source="ui",
                    )
                    with state.inference_lock:
                        last_result = state.inference.predict(frame_obj)
                    last_quality_ok = quality_gate(last_result)
                    decision = decision_engine.process(
                        inference=last_result,
                        ingestion_ok=True,
                        quality_ok=last_quality_ok,
                        frame_id=frame_obj.frame_id,
                        timestamp=frame_obj.timestamp,
                    )
                    processed += 1
            finally:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

        if last_result is None:
            raise HTTPException(status_code=400, detail="No frames processed")

        decision_payload = decision.__dict__ if decision else {}
        if decision and decision.class_id and state.mapper is not None:
            map_result = state.mapper.map_class(decision.class_id)
            decision_payload["code"] = map_result.code
            decision_payload["mapping_reason"] = map_result.reason

        return {
            "mode": "video" if is_video else "image",
            "frames_processed": processed,
            "quality_ok": last_quality_ok,
            "top_k": _map_top_k(state, last_result),
            "decision": decision_payload,
        }

    return app
