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
    <title>ScaleUP - Fruits & Vegetables Detector</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #e9f7ff;
        --bg-2: #e8fff5;
        --panel: #f7fffb;
        --card: #ffffff;
        --text: #0f172a;
        --muted: #475569;
        --accent: #1d4ed8;
        --accent-2: #16a34a;
        --accent-3: #0ea5e9;
        --border: rgba(15, 23, 42, 0.16);
        --shadow: 0 18px 45px rgba(15, 23, 42, 0.14);
        --warn: #c2410c;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Ubuntu", "Cantarell", "DejaVu Sans", sans-serif;
        background: radial-gradient(900px 500px at 12% -10%, #b3ddff, transparent),
                    radial-gradient(800px 450px at 110% 18%, #bff5d8, transparent),
                    linear-gradient(180deg, var(--bg), var(--bg-2));
        color: var(--text);
        min-height: 100vh;
        position: relative;
      }
      body::before,
      body::after {
        content: "";
        position: fixed;
        z-index: 0;
        border-radius: 40%;
        opacity: 0.6;
        pointer-events: none;
      }
      body::before {
        width: 260px;
        height: 260px;
        top: -70px;
        right: -50px;
        background: rgba(29, 78, 216, 0.18);
      }
      body::after {
        width: 320px;
        height: 320px;
        bottom: -120px;
        left: -80px;
        background: rgba(22, 163, 74, 0.16);
      }
      header,
      main,
      footer {
        position: relative;
        z-index: 1;
      }
      header {
        padding: 28px 32px 14px;
        display: flex;
        justify-content: space-between;
        gap: 24px;
        flex-wrap: wrap;
        align-items: flex-end;
      }
      .eyebrow {
        text-transform: uppercase;
        letter-spacing: 2px;
        font-size: 11px;
        color: var(--muted);
      }
      header h1 {
        margin: 6px 0;
        font-size: 30px;
      }
      header p {
        margin: 0;
        color: var(--muted);
        max-width: 480px;
      }
      .header-meta {
        display: grid;
        gap: 8px;
        justify-items: end;
      }
      main {
        padding: 8px 32px 36px;
        display: grid;
        grid-template-columns: minmax(280px, 1.1fr) minmax(320px, 1.4fr);
        gap: 18px;
      }
      .panel {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 18px;
        box-shadow: var(--shadow);
        animation: rise 0.6s ease both;
      }
      .panel:nth-child(2) { animation-delay: 0.08s; }
      @keyframes rise {
        from { opacity: 0; transform: translateY(16px); }
        to { opacity: 1; transform: translateY(0); }
      }
      @media (prefers-reduced-motion: reduce) {
        .panel { animation: none; }
      }
      .panel-header {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: center;
        margin-bottom: 10px;
      }
      h2 {
        margin: 0;
        font-size: 18px;
      }
      h3 {
        margin: 0 0 6px;
        font-size: 14px;
        color: var(--accent);
      }
      .pills {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .pill {
        padding: 6px 12px;
        border-radius: 999px;
        font-size: 12px;
        border: 1px solid var(--border);
        background: #f0f9ff;
      }
      .pill.accent {
        background: rgba(22, 163, 74, 0.16);
        border-color: rgba(22, 163, 74, 0.4);
        color: #14532d;
      }
      .pill.ok { border-color: rgba(22, 163, 74, 0.6); color: #14532d; }
      .pill.warn { border-color: rgba(194, 65, 12, 0.6); color: var(--warn); }
      .meta {
        font-size: 12px;
        color: var(--muted);
        margin-top: 6px;
      }
      .status-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 10px;
        margin-top: 12px;
      }
      .status-card {
        background: var(--card);
        border: 1px solid rgba(148, 163, 184, 0.4);
        border-radius: 14px;
        padding: 12px;
        min-height: 140px;
      }
      .controls {
        display: grid;
        gap: 12px;
      }
      .file-drop {
        border: 2px dashed #93c5fd;
        background: #eff6ff;
        border-radius: 16px;
        padding: 14px;
        display: grid;
        gap: 4px;
        cursor: pointer;
      }
      .file-drop input {
        display: none;
      }
      .file-drop span {
        font-weight: 600;
        color: var(--accent);
      }
      .file-drop small {
        color: var(--muted);
      }
      .button-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }
      button {
        background: #1d4ed8;
        color: #ecfeff;
        font-weight: 600;
        border: none;
        border-radius: 12px;
        padding: 10px 14px;
        cursor: pointer;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        box-shadow: 0 10px 18px rgba(29, 78, 216, 0.25);
      }
      button:hover { transform: translateY(-1px); }
      button.ghost {
        background: #eafff2;
        color: #14532d;
        border: 1px solid rgba(22, 163, 74, 0.4);
        box-shadow: none;
      }
      .detect-grid {
        display: grid;
        grid-template-columns: minmax(240px, 1fr) minmax(260px, 1fr);
        gap: 14px;
      }
      .preview-frame {
        position: relative;
        background: #f8fafc;
        border-radius: 16px;
        border: 2px solid #bae6fd;
        padding: 12px;
        min-height: 260px;
        display: grid;
        place-items: center;
        overflow: hidden;
      }
      .preview-frame img,
      .preview-frame video {
        width: 100%;
        border-radius: 12px;
        display: none;
      }
      .placeholder {
        text-align: center;
        color: var(--muted);
        font-size: 13px;
      }
      pre {
        margin: 0;
        font-size: 12px;
        line-height: 1.5;
        white-space: pre-wrap;
        word-break: break-word;
      }
      footer {
        padding: 0 32px 28px;
        color: var(--muted);
        font-size: 12px;
      }
      @media (max-width: 980px) {
        main {
          grid-template-columns: 1fr;
        }
        .detect-grid {
          grid-template-columns: 1fr;
        }
        .header-meta {
          justify-items: start;
        }
      }
    </style>
  </head>
  <body>
    <header>
      <div>
        <div class="eyebrow">ScaleUP Local UI</div>
        <h1>Fruits & Vegetables Detector</h1>
        <p>Use this console to validate recognition, mapping, and camera input on Ubuntu.</p>
      </div>
      <div class="header-meta">
        <span class="pill" id="version">loading version...</span>
        <span class="pill accent" id="model-status">model: loading...</span>
      </div>
    </header>
    <main>
      <section class="panel">
        <div class="panel-header">
          <h2>System Status</h2>
          <button id="refreshButton" class="ghost">Refresh Status</button>
        </div>
        <div class="pills" id="health-badges"></div>
        <div class="meta" id="health-meta"></div>
        <div class="status-grid">
          <div class="status-card">
            <h3>Ingestion</h3>
            <pre id="ingestion"></pre>
          </div>
          <div class="status-card">
            <h3>Last Decision</h3>
            <pre id="decision"></pre>
          </div>
          <div class="status-card">
            <h3>Output + Safety</h3>
            <pre id="system"></pre>
          </div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-header">
          <h2>Detection Console</h2>
          <div class="pills">
            <span class="pill accent">Local API</span>
            <span class="pill" id="health-state">ready=...</span>
          </div>
        </div>
        <div class="detect-grid">
          <div class="controls">
            <label class="file-drop">
              <input id="fileInput" type="file" accept="image/*,video/*" />
              <span>Choose Image or Video</span>
              <small id="previewLabel">No file selected</small>
            </label>
            <div class="button-row">
              <button id="loadButton" class="ghost">Load Model / Refresh</button>
              <button id="runButton">Classify File</button>
              <button id="cameraStart" class="ghost">Start Camera</button>
              <button id="cameraCapture" class="ghost">Capture + Classify</button>
            </div>
            <div>
              <h3>File Result</h3>
              <pre id="predict"></pre>
            </div>
            <div>
              <h3>Camera Result</h3>
              <pre id="cameraResult"></pre>
            </div>
          </div>
          <div>
            <div class="preview-frame">
              <div id="previewPlaceholder" class="placeholder">Select a file or start the camera.</div>
              <img id="previewImage" alt="preview" />
              <video id="previewVideo" controls></video>
              <video id="camera" autoplay playsinline></video>
              <canvas id="canvas" style="display:none;"></canvas>
            </div>
            <div class="meta">The preview area follows the load, choose, and classify flow for validation.</div>
          </div>
        </div>
      </section>
    </main>
    <footer>ScaleUP runs locally. If /health returns 404, check the service port in /etc/scale-vision/config.json.</footer>
    <script>
      const el = (id) => document.getElementById(id);
      const pretty = (obj) => JSON.stringify(obj, null, 2);
      let previewUrl = null;
      let stream = null;

      function showPreview(mode) {
        el("previewPlaceholder").style.display = mode === "empty" ? "block" : "none";
        el("previewImage").style.display = mode === "image" ? "block" : "none";
        el("previewVideo").style.display = mode === "video" ? "block" : "none";
        el("camera").style.display = mode === "camera" ? "block" : "none";
      }

      function resetPreview() {
        if (previewUrl) {
          URL.revokeObjectURL(previewUrl);
          previewUrl = null;
        }
        el("previewImage").src = "";
        el("previewVideo").src = "";
        showPreview("empty");
      }

      function stopCamera() {
        if (stream) {
          stream.getTracks().forEach((track) => track.stop());
          stream = null;
        }
        el("camera").srcObject = null;
      }

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
          el("model-status").textContent = `model: ${system.inference_backend || "unknown"}`;
          const badges = [];
          const pillClass = health.degraded ? "warn" : "ok";
          badges.push(`<span class="pill ${pillClass}">ready=${health.ready}</span>`);
          badges.push(`<span class="pill ${pillClass}">degraded=${health.degraded}</span>`);
          el("health-badges").innerHTML = badges.join("");
          el("health-state").textContent = `ready=${health.ready}`;
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

      el("fileInput").addEventListener("change", () => {
        const file = el("fileInput").files[0];
        el("predict").textContent = "";
        stopCamera();
        if (!file) {
          el("previewLabel").textContent = "No file selected";
          resetPreview();
          return;
        }
        el("previewLabel").textContent = file.name;
        if (previewUrl) {
          URL.revokeObjectURL(previewUrl);
        }
        previewUrl = URL.createObjectURL(file);
        if (file.type.startsWith("image/")) {
          el("previewImage").src = previewUrl;
          showPreview("image");
        } else if (file.type.startsWith("video/")) {
          el("previewVideo").src = previewUrl;
          showPreview("video");
          el("previewVideo").play().catch(() => {});
        } else {
          el("previewLabel").textContent = "Unsupported file type";
          resetPreview();
        }
      });

      el("runButton").addEventListener("click", () => {
        const file = el("fileInput").files[0];
        if (!file) {
          el("predict").textContent = "Please select an image or video.";
          return;
        }
        runPredict(file, el("predict"));
      });

      el("refreshButton").addEventListener("click", refreshStatus);
      el("loadButton").addEventListener("click", refreshStatus);

      el("cameraStart").addEventListener("click", async () => {
        try {
          stream = await navigator.mediaDevices.getUserMedia({ video: true });
          el("camera").srcObject = stream;
          showPreview("camera");
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

      resetPreview();
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
