from __future__ import annotations

import glob
import hashlib
import json
import os
import stat
import subprocess
import tempfile
import time
from typing import Dict, List, Optional

import cv2
import numpy as np
from fastapi import Body, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse

from scale_vision.config.models import AppConfig
from scale_vision.decision.quality import quality_gate
from scale_vision.decision.state_machine import DecisionEngine
from scale_vision.ingestion.normalization import normalize_frame
from scale_vision.state import RuntimeState
from scale_vision.types import ClassProb, Frame, InferenceResult
from scale_vision.versioning import app_version

_UI_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>ScaleUP - Recognition Console</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #f5f7fb;
        --panel: #ffffff;
        --text: #0f172a;
        --muted: #5b677a;
        --accent: #1f4fff;
        --accent-2: #0f9d58;
        --danger: #b91c1c;
        --border: rgba(15, 23, 42, 0.12);
        --shadow: 0 18px 40px rgba(15, 23, 42, 0.10);
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "Space Grotesk", "Ubuntu", "DejaVu Sans", sans-serif;
        color: var(--text);
        background: radial-gradient(900px 520px at 8% -10%, #d6e2ff, transparent),
                    radial-gradient(820px 460px at 110% 18%, #c9f1db, transparent),
                    var(--bg);
        min-height: 100vh;
      }
      header {
        padding: 24px 32px 8px;
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 18px;
      }
      .title-block {
        max-width: 520px;
      }
      .eyebrow {
        text-transform: uppercase;
        letter-spacing: 2px;
        font-size: 11px;
        color: var(--muted);
      }
      h1 {
        margin: 8px 0 6px;
        font-size: 28px;
      }
      p {
        margin: 0;
        color: var(--muted);
      }
      .status-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        justify-content: flex-end;
      }
      .screen {
        display: none;
      }
      .screen.active {
        display: block;
      }
      .home {
        min-height: 100vh;
        display: grid;
        place-items: center;
        padding: 32px;
      }
      .home-card {
        max-width: 760px;
        width: 100%;
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 20px;
        padding: 28px;
        box-shadow: var(--shadow);
        display: grid;
        gap: 20px;
      }
      .home-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 14px;
      }
      .home-option {
        border: 1px solid rgba(148, 163, 184, 0.35);
        border-radius: 14px;
        padding: 16px;
        background: #f8fafc;
        display: grid;
        gap: 10px;
      }
      .home-option h3 {
        margin: 0;
        font-size: 16px;
      }
      .home-option p {
        margin: 0;
        color: var(--muted);
        font-size: 13px;
      }
      .pill {
        padding: 6px 12px;
        border-radius: 999px;
        font-size: 12px;
        border: 1px solid var(--border);
        background: #eef2ff;
      }
      .pill.ok { background: rgba(15, 157, 88, 0.12); border-color: rgba(15, 157, 88, 0.5); color: #0f9d58; }
      .pill.warn { background: rgba(185, 28, 28, 0.12); border-color: rgba(185, 28, 28, 0.5); color: #b91c1c; }
      main {
        padding: 12px 32px 32px;
        display: grid;
        grid-template-columns: minmax(320px, 1.1fr) minmax(320px, 1fr);
        gap: 18px;
      }
      .panel {
        background: var(--panel);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 18px;
        box-shadow: var(--shadow);
      }
      .panel h2 {
        margin: 0 0 12px;
        font-size: 17px;
      }
      .config-panel {
        margin: 0 32px 32px;
      }
      .config-grid {
        display: grid;
        grid-template-columns: minmax(260px, 1fr) minmax(260px, 1fr);
        gap: 16px;
      }
      .config-card {
        border: 1px solid rgba(148, 163, 184, 0.35);
        border-radius: 14px;
        padding: 14px;
        background: #f8fafc;
        display: grid;
        gap: 10px;
      }
      .config-card.full {
        grid-column: 1 / -1;
      }
      .field {
        display: grid;
        gap: 6px;
        font-size: 13px;
      }
      .field label {
        color: var(--muted);
        font-weight: 600;
        font-size: 12px;
      }
      .field input {
        padding: 9px 12px;
        border-radius: 10px;
        border: 1px solid rgba(148, 163, 184, 0.5);
        font-weight: 600;
        color: #334155;
      }
      textarea {
        width: 100%;
        min-height: 200px;
        padding: 10px 12px;
        border-radius: 10px;
        border: 1px solid rgba(148, 163, 184, 0.5);
        font-family: "JetBrains Mono", "Fira Code", "Ubuntu Mono", monospace;
        font-size: 12px;
        color: #0f172a;
        background: #fff;
      }
      .mapping-table {
        display: grid;
        gap: 6px;
        max-height: 260px;
        overflow: auto;
      }
      .mapping-row {
        display: grid;
        grid-template-columns: 1.2fr 0.8fr;
        gap: 8px;
        padding: 8px 10px;
        border-radius: 10px;
        background: #fff;
        border: 1px solid rgba(148, 163, 184, 0.25);
        font-size: 12px;
      }
      .file-drop {
        border: 2px dashed #c7d2fe;
        background: #f8faff;
        border-radius: 14px;
        padding: 14px;
        display: grid;
        gap: 6px;
        cursor: pointer;
      }
      .file-drop input { display: none; }
      .file-drop span { font-weight: 600; color: var(--accent); }
      .file-drop small { color: var(--muted); }
      .button-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }
      select {
        padding: 9px 12px;
        border-radius: 10px;
        border: 1px solid rgba(148, 163, 184, 0.5);
        background: #fff;
        font-weight: 600;
        color: #334155;
      }
      button {
        background: var(--accent);
        color: #fff;
        font-weight: 600;
        border: none;
        border-radius: 10px;
        padding: 10px 14px;
        cursor: pointer;
        transition: transform 0.2s ease;
      }
      button:hover { transform: translateY(-1px); }
      button.ghost {
        background: #ecfdf3;
        color: #0f9d58;
        border: 1px solid rgba(15, 157, 88, 0.35);
      }
      button.subtle {
        background: #f1f5f9;
        color: #334155;
        border: 1px solid rgba(148, 163, 184, 0.5);
      }
      .preview-frame {
        margin-top: 12px;
        position: relative;
        background: #f8fafc;
        border-radius: 14px;
        border: 1px solid rgba(148, 163, 184, 0.4);
        padding: 10px;
        min-height: 220px;
        display: grid;
        place-items: center;
      }
      .preview-frame img,
      .preview-frame video {
        width: 100%;
        border-radius: 10px;
        display: none;
      }
      .placeholder {
        text-align: center;
        color: var(--muted);
        font-size: 13px;
      }
      .result-card {
        border: 1px solid rgba(148, 163, 184, 0.4);
        border-radius: 14px;
        padding: 14px;
        display: grid;
        gap: 8px;
      }
      .divider {
        margin: 14px 0 6px;
        text-align: center;
        text-transform: uppercase;
        letter-spacing: 1.4px;
        font-size: 11px;
        color: var(--muted);
      }
      .result-title {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        align-items: center;
      }
      .result-name { font-size: 22px; font-weight: 700; }
      .result-code { font-size: 13px; color: var(--muted); }
      .progress {
        height: 8px;
        background: #e2e8f0;
        border-radius: 999px;
        overflow: hidden;
      }
      .progress span {
        display: block;
        height: 100%;
        width: 0;
        background: linear-gradient(90deg, #0f9d58, #1f4fff);
      }
      .top-list {
        display: grid;
        gap: 8px;
      }
      .top-item {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        padding: 8px 10px;
        border-radius: 10px;
        background: #f8fafc;
        border: 1px solid rgba(148, 163, 184, 0.35);
        font-size: 13px;
      }
      .top-item small { color: var(--muted); }
      details {
        margin-top: 12px;
      }
      pre {
        margin: 8px 0 0;
        font-size: 11px;
        line-height: 1.5;
        white-space: pre-wrap;
        word-break: break-word;
      }
      .hint {
        margin-top: 6px;
        font-size: 12px;
        color: var(--muted);
      }
      footer {
        padding: 0 32px 24px;
        font-size: 12px;
        color: var(--muted);
      }
      @media (max-width: 980px) {
        header { padding: 22px 20px 6px; }
        main { grid-template-columns: 1fr; padding: 10px 20px 24px; }
        .status-row { justify-content: flex-start; }
        .config-panel { margin: 0 20px 24px; }
        .config-grid { grid-template-columns: 1fr; }
      }
    </style>
  </head>
  <body>
    <div id="homeScreen" class="screen active">
      <div class="home">
        <div class="home-card">
          <div>
            <div class="eyebrow">ScaleUP Local</div>
            <h1>Selecciona un módulo</h1>
            <p>Elige entre la consola de reconocimiento o la configuración ETPOS.</p>
          </div>
          <div class="home-grid">
            <div class="home-option">
              <h3>Reconocimiento</h3>
              <p>Prueba el modelo con imágenes o cámara.</p>
              <button id="openRecognition">Abrir consola</button>
            </div>
            <div class="home-option">
              <h3>ETPOS</h3>
              <p>Configura salida y revisa códigos de productos.</p>
              <button id="openEtpos" class="ghost">Abrir configuración</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div id="recognitionScreen" class="screen">
      <header>
        <div class="title-block">
          <div class="eyebrow">ScaleUP Local</div>
          <h1>Recognition Console</h1>
          <p>Carga una imagen o usa la cámara para validar reconocimiento y mapeo.</p>
        </div>
        <div class="status-row">
          <button id="backHomeFromRecognition" class="subtle">Volver al inicio</button>
          <span class="pill" id="connection-pill">service...</span>
          <span class="pill" id="version">version...</span>
          <span class="pill" id="model-status">model...</span>
          <span class="pill" id="mapping-status">mapping...</span>
        </div>
      </header>
      <main>
        <section class="panel">
          <h2>Entrada</h2>
          <label class="file-drop">
            <input id="fileInput" type="file" accept="image/*,video/*" />
            <span>Cargar foto o video</span>
            <small id="previewLabel">Sin archivo</small>
          </label>
          <div class="divider">o usar cámara</div>
          <div class="button-row" style="margin-top:12px;">
            <button id="clearButton" class="subtle">Limpiar</button>
          </div>
          <div class="button-row" style="margin-top:12px;">
            <select id="cameraSelect"></select>
            <button id="cameraAction" class="ghost">Usar cámara</button>
            <button id="cameraStop" class="subtle">Detener</button>
            <button id="refreshCameras" class="subtle">Actualizar</button>
          </div>
          <div id="cameraHint" class="hint">Detectando cámaras...</div>
          <div class="preview-frame">
            <div id="previewPlaceholder" class="placeholder">Selecciona un archivo o inicia la cámara.</div>
            <img id="cameraStream" alt="camera stream" />
            <img id="previewImage" alt="preview" />
            <video id="previewVideo" controls></video>
            <canvas id="cameraCanvas" style="display:none;"></canvas>
          </div>
        </section>
        <section class="panel">
          <h2>Resultado</h2>
          <div class="result-card">
            <div class="result-title">
              <div class="result-name" id="best-class">Sin predicción</div>
              <div class="result-code" id="best-code">código: -</div>
            </div>
            <div class="progress"><span id="best-bar"></span></div>
            <div class="result-code" id="best-meta">confianza: -</div>
          </div>
          <div style="margin-top:12px;">
            <div class="result-code" style="margin-bottom:6px;">Mejores coincidencias</div>
            <div id="aggregate-list" class="top-list"></div>
          </div>
          <details>
            <summary>Respuesta cruda</summary>
            <pre id="predict"></pre>
          </details>
          <details>
            <summary>Respuesta cámara</summary>
            <pre id="cameraResult"></pre>
          </details>
        </section>
      </main>
    </div>

    <div id="etposScreen" class="screen">
      <header>
        <div class="title-block">
          <div class="eyebrow">ScaleUP Local</div>
          <h1>ETPOS configuración</h1>
          <p>Configura la salida y revisa códigos para ETPOS.</p>
        </div>
        <div class="status-row">
          <button id="backHomeFromEtpos" class="subtle">Volver al inicio</button>
        </div>
      </header>
      <section class="panel config-panel">
        <div class="config-grid">
          <div class="config-card">
            <div class="result-code">Conexión</div>
            <div class="field">
              <label>Salida (backend)</label>
              <select id="outputBackend">
                <option value="test">test</option>
                <option value="serial">serial</option>
                <option value="hid">hid</option>
              </select>
            </div>
            <div class="field">
              <label>Puerto serial</label>
              <input id="serialDevice" placeholder="/dev/ttyUSB0" />
            </div>
            <div class="field">
              <label>Baudrate</label>
              <input id="serialBaud" type="number" min="1200" step="100" />
            </div>
            <div class="field">
              <label>Paridad</label>
              <select id="serialParity">
                <option value="none">none</option>
                <option value="even">even</option>
                <option value="odd">odd</option>
              </select>
            </div>
            <div class="field">
              <label>Stopbits</label>
              <select id="serialStopbits">
                <option value="1">1</option>
                <option value="2">2</option>
              </select>
            </div>
            <div class="field">
              <label>Terminador</label>
              <input id="serialTerminator" placeholder="\\r\\n" />
            </div>
            <div class="button-row">
              <button id="saveConfig">Guardar</button>
              <button id="applyConfig" class="ghost">Guardar y reiniciar</button>
              <button id="restartService" class="subtle">Reiniciar servicio</button>
            </div>
            <div id="configStatus" class="hint">Carga la configuración para ver el estado.</div>
          </div>
          <div class="config-card">
            <div class="result-code">Productos reconocidos</div>
            <div class="field">
              <label>Filtro</label>
              <input id="mappingFilter" placeholder="Buscar clase o código" />
            </div>
            <div id="mappingTable" class="mapping-table"></div>
          </div>
          <div class="config-card full">
            <div class="result-code">Configuración avanzada (JSON)</div>
            <div class="field">
              <label>Config actual</label>
              <textarea id="configRaw" placeholder="{ ... }"></textarea>
            </div>
            <div class="button-row">
              <button id="loadConfigRaw" class="subtle">Recargar JSON</button>
              <button id="saveConfigRaw">Guardar JSON</button>
            </div>
            <div id="configRawStatus" class="hint">Carga el JSON para editarlo.</div>
          </div>
        </div>
      </section>
    </div>
    <script>
      const el = (id) => document.getElementById(id);
      const pretty = (obj) => JSON.stringify(obj, null, 2);
      let previewUrl = null;
      let activeCamera = null;
      let cameraActive = false;
      let autoTimer = null;
      let captureInFlight = false;
      const autoIntervalMs = 1000;
      let normalizeWidth = 640;
      let normalizeHeight = 640;
      let activeMode = "idle";
      let cameraRetryTimer = null;
      let cameraRetryCount = 0;
      const cameraRetryMax = 3;

      function setScreen(name) {
        const screens = {
          home: el("homeScreen"),
          recognition: el("recognitionScreen"),
          etpos: el("etposScreen"),
        };
        Object.values(screens).forEach((node) => {
          if (node) node.classList.remove("active");
        });
        if (name === "home") {
          stopCamera();
          resetPreview();
          resetResults();
        }
        screens[name]?.classList.add("active");
      }

      function showPreview(mode) {
        el("previewPlaceholder").style.display = mode === "empty" ? "block" : "none";
        el("previewImage").style.display = mode === "image" ? "block" : "none";
        el("previewVideo").style.display = mode === "video" ? "block" : "none";
        el("cameraStream").style.display = mode === "camera" ? "block" : "none";
      }

      function resetPreview() {
        if (previewUrl) {
          URL.revokeObjectURL(previewUrl);
          previewUrl = null;
        }
        el("previewImage").src = "";
        el("previewVideo").src = "";
        el("cameraStream").src = "";
        showPreview("empty");
      }

      function stopCamera() {
        const img = el("cameraStream");
        if (img) {
          img.src = "about:blank";
          img.removeAttribute("src");
        }
        activeCamera = null;
        cameraActive = false;
        activeMode = "idle";
        setCameraUi(false);
        el("cameraHint").textContent = "Cámara detenida";
        captureInFlight = false;
        if (autoTimer) {
          clearInterval(autoTimer);
          autoTimer = null;
        }
        if (cameraRetryTimer) {
          clearTimeout(cameraRetryTimer);
          cameraRetryTimer = null;
        }
        cameraRetryCount = 0;
        resetCameraElement();
      }

      function resetResults() {
        el("predict").textContent = "";
        el("cameraResult").textContent = "";
        el("best-class").textContent = "Sin predicción";
        el("best-code").textContent = "código: -";
        el("best-meta").textContent = "confianza: -";
        el("best-bar").style.width = "0%";
        el("aggregate-list").innerHTML = "<div class='result-code'>Aún no hay resultados.</div>";
      }

      function setCameraUi(active) {
        const action = el("cameraAction");
        const stopBtn = el("cameraStop");
        cameraActive = active;
        if (action) action.textContent = active ? "Capturar ahora" : "Iniciar cámara";
        if (stopBtn) stopBtn.style.display = active ? "inline-flex" : "none";
      }

      function bindCameraStreamEvents() {
        const img = el("cameraStream");
        if (!img) return;
        img.addEventListener("load", () => {
          if (cameraActive) {
            el("cameraHint").textContent = "Cámara lista (auto cada 1s)";
          }
          cameraRetryCount = 0;
          if (cameraRetryTimer) {
            clearTimeout(cameraRetryTimer);
            cameraRetryTimer = null;
          }
        });
        img.addEventListener("error", () => {
          if (!cameraActive && activeMode !== "camera") {
            return;
          }
          cameraRetryCount += 1;
          if (cameraRetryCount <= cameraRetryMax) {
            el("cameraHint").textContent = `Error al cargar cámara. Reintentando (${cameraRetryCount}/${cameraRetryMax})...`;
            if (cameraRetryTimer) clearTimeout(cameraRetryTimer);
            cameraRetryTimer = setTimeout(() => {
              startCameraStream();
            }, 700 * cameraRetryCount);
          } else {
            el("cameraHint").textContent = "Error al cargar cámara";
            setCameraUi(false);
          }
        });
      }

      function resetCameraElement() {
        const img = el("cameraStream");
        if (!img) return;
        const fresh = img.cloneNode(false);
        fresh.id = "cameraStream";
        fresh.alt = img.alt || "camera stream";
        fresh.removeAttribute("src");
        img.replaceWith(fresh);
        bindCameraStreamEvents();
      }

      function setConnection(state, label) {
        const pill = el("connection-pill");
        pill.classList.remove("ok", "warn");
        pill.textContent = label;
        if (state === "ok") pill.classList.add("ok");
        if (state === "warn") pill.classList.add("warn");
      }

      function guessFileKind(file) {
        const name = (file.name || "").toLowerCase();
        const type = (file.type || "").toLowerCase();
        const isImage = type.startsWith("image/") || /\.(png|jpg|jpeg|bmp|gif|webp)$/i.test(name);
        const isVideo = type.startsWith("video/") || /\.(mp4|mov|avi|mkv|webm)$/i.test(name);
        return { isImage, isVideo };
      }

      async function fetchJson(path) {
        const res = await fetch(path, { cache: "no-store" });
        if (!res.ok) throw new Error(await res.text());
        return res.json();
      }

      async function loadCameras() {
        try {
          const data = await fetchJson("/ui/camera/devices");
          const devices = data.devices || [];
          const select = el("cameraSelect");
          if (!devices.length) {
            select.innerHTML = "<option value=''>Sin cámaras</option>";
            select.disabled = true;
            el("cameraHint").textContent = "No se detectaron cámaras en el servicio.";
            return;
          }
          select.disabled = false;
          select.innerHTML = devices
            .map((device) => `<option value="${device.path}">${device.name || device.path}</option>`)
            .join("");
          activeCamera = select.value;
          el("cameraHint").textContent = `${devices.length} cámara(s) detectada(s)`;
        } catch (err) {
          el("cameraSelect").innerHTML = "<option value=''>Lista no disponible</option>";
          el("cameraSelect").disabled = true;
          el("cameraHint").textContent = `Error de cámara: ${err}`;
        }
      }

      function renderTopList(items) {
        if (!items || !items.length) {
          el("aggregate-list").innerHTML = "<div class='result-code'>Sin predicciones aún.</div>";
          return;
        }
        const rows = items.slice(0, 4).map((item) => {
          const pct = Math.round((item.prob || 0) * 100);
          const code = item.code ? `código ${item.code}` : "sin mapa";
          return `
            <div class='top-item'>
              <div>
                <strong>${item.class_id}</strong><br />
                <small>${code}</small>
              </div>
              <div>${pct}%</div>
            </div>`;
        });
        el("aggregate-list").innerHTML = rows.join("");
      }

      async function captureCamera() {
        const device = activeCamera || (el("cameraSelect") && el("cameraSelect").value) || "/dev/video0";
        if (!device) {
          el("cameraResult").textContent = "Cámara no iniciada.";
          return;
        }
        if (captureInFlight) return;
        const img = el("cameraStream");
        if (cameraActive && (!img || !img.src || !img.naturalWidth)) {
          el("cameraResult").textContent = "Cámara iniciándose, espera un momento.";
          return;
        }
        if (img && img.src && img.naturalWidth) {
          const canvas = el("cameraCanvas");
          const targetWidth = normalizeWidth || 640;
          const ratio = img.naturalWidth ? targetWidth / img.naturalWidth : 1;
          canvas.width = targetWidth;
          canvas.height = Math.max(1, Math.round((img.naturalHeight || 480) * ratio));
          const ctx = canvas.getContext("2d");
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
          captureInFlight = true;
          canvas.toBlob((blob) => {
            if (!blob) {
              el("cameraResult").textContent = "No se pudo capturar el frame.";
              captureInFlight = false;
              return;
            }
            const file = new File([blob], "camera.jpg", { type: "image/jpeg" });
            runPredict(file, el("cameraResult")).finally(() => {
              captureInFlight = false;
            });
          }, "image/jpeg", 0.85);
          return;
        }
        try {
          captureInFlight = true;
          const res = await fetch(`/ui/camera/frame?device=${encodeURIComponent(device)}`, { cache: "no-store" });
          if (!res.ok) throw new Error(await res.text());
          const blob = await res.blob();
          const file = new File([blob], "camera.jpg", { type: "image/jpeg" });
          runPredict(file, el("cameraResult"));
        } catch (err) {
          el("cameraResult").textContent = `Error de cámara: ${err}`;
        } finally {
          captureInFlight = false;
        }
      }

      function startAutoCapture() {
        if (autoTimer) clearInterval(autoTimer);
        autoTimer = setInterval(() => {
          if (cameraActive) {
            captureCamera();
          }
        }, autoIntervalMs);
      }

      async function startCameraStream() {
        stopCamera();
        const select = el("cameraSelect");
        const device = select && select.value ? select.value : "/dev/video0";
        if (!device) {
          el("cameraResult").textContent = "No hay cámara seleccionada.";
          return;
        }
        activeMode = "camera";
        el("fileInput").value = "";
        el("previewLabel").textContent = "Sin archivo";
        activeCamera = device;
        cameraRetryCount = 0;
        el("cameraHint").textContent = "Iniciando cámara (auto cada 1s)...";
        el("cameraStream").src = `/ui/camera/stream?device=${encodeURIComponent(device)}&t=${Date.now()}`;
        showPreview("camera");
        setCameraUi(true);
        startAutoCapture();
      }

      function updateBestGuess(best) {
        if (!best) {
          el("best-class").textContent = "Sin predicción";
          el("best-code").textContent = "código: -";
          el("best-meta").textContent = "confianza: -";
          el("best-bar").style.width = "0%";
          return;
        }
        const pct = Math.round((best.prob || 0) * 100);
        el("best-class").textContent = best.class_id || "Unknown";
        el("best-code").textContent = `código: ${best.code || "sin mapa"}`;
        el("best-meta").textContent = `confianza: ${pct}% (${best.mapping_reason || "-"})`;
        el("best-bar").style.width = `${pct}%`;
      }

      async function refreshStatus() {
        try {
          const health = await fetchJson("/health");
          const system = await fetchJson("/ui/status");
          setConnection("ok", "service online");
          el("version").textContent = `version ${health.version} (${health.build_id})`;
          const activeModel = system.inference_backend || "unknown";
          const configuredModel = system.configured_backend || activeModel;
          el("model-status").textContent = configuredModel !== activeModel
            ? `model: ${activeModel} (cfg: ${configuredModel})`
            : `model: ${activeModel}`;
          el("mapping-status").textContent = `mapping: ${system.mapping_count || 0} | labels: ${system.labels_count || 0}`;
          if (system.normalize_width) normalizeWidth = system.normalize_width;
          if (system.normalize_height) normalizeHeight = system.normalize_height;
        } catch (err) {
          setConnection("warn", "service offline");
        }
      }

      function renderMappingTable(items) {
        const table = el("mappingTable");
        if (!items || !items.length) {
          table.innerHTML = "<div class='result-code'>Sin productos configurados.</div>";
          return;
        }
        table.innerHTML = items.map((item) => {
          const code = item.code ? `${item.code_type || "code"} ${item.code}` : "sin código";
          return `<div class="mapping-row"><div>${item.class_id}</div><div>${code}</div></div>`;
        }).join("");
      }

      async function refreshMapping() {
        try {
          const data = await fetchJson("/ui/mapping");
          renderMappingTable(data.items || []);
        } catch (err) {
          el("mappingTable").innerHTML = `<div class='result-code'>Error: ${err}</div>`;
        }
      }

      async function refreshConfig() {
        try {
          const data = await fetchJson("/ui/config");
          const output = data.output || {};
          const serial = output.serial || {};
          el("outputBackend").value = output.backend || "test";
          el("serialDevice").value = serial.device || "";
          el("serialBaud").value = serial.baudrate || 9600;
          el("serialParity").value = serial.parity || "none";
          el("serialStopbits").value = String(serial.stopbits || 1);
          el("serialTerminator").value = serial.terminator || "\\r\\n";
          el("configStatus").textContent = data.writable
            ? "Config editable. Guardar aplica al config.json."
            : "Sin permisos de escritura. Ajusta /etc/scale-vision/config.json.";
        } catch (err) {
          el("configStatus").textContent = `Error cargando config: ${err}`;
        }
      }

      el("saveConfig").addEventListener("click", async () => {
        const payload = {
          output: {
            backend: el("outputBackend").value,
            serial: {
              device: el("serialDevice").value,
              baudrate: Number(el("serialBaud").value || 9600),
              parity: el("serialParity").value,
              stopbits: Number(el("serialStopbits").value || 1),
              terminator: el("serialTerminator").value,
            },
          },
        };
        try {
          const res = await fetch("/ui/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          if (!res.ok) throw new Error(await res.text());
          el("configStatus").textContent = "Config guardada. Reinicia el servicio para aplicar.";
          refreshConfig();
        } catch (err) {
          el("configStatus").textContent = `Error guardando: ${err}`;
        }
      });

      el("mappingFilter").addEventListener("input", async (event) => {
        const query = (event.target.value || "").toLowerCase();
        try {
          const data = await fetchJson("/ui/mapping");
          const items = (data.items || []).filter((item) => {
            return (
              item.class_id.toLowerCase().includes(query) ||
              String(item.code || "").toLowerCase().includes(query)
            );
          });
          renderMappingTable(items);
        } catch (err) {
          el("mappingTable").innerHTML = `<div class='result-code'>Error: ${err}</div>`;
        }
      });

      el("restartService").addEventListener("click", async () => {
        try {
          const res = await fetch("/ui/service/restart", { method: "POST" });
          if (!res.ok) throw new Error(await res.text());
          el("configStatus").textContent = "Reinicio solicitado. Espera unos segundos.";
        } catch (err) {
          el("configStatus").textContent = `Error reiniciando: ${err}`;
        }
      });

      async function waitForHealth(timeoutMs = 12000) {
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
          try {
            const res = await fetch("/health", { cache: "no-store" });
            if (res.ok) return true;
          } catch (err) {
            // ignore while restarting
          }
          await new Promise((resolve) => setTimeout(resolve, 700));
        }
        return false;
      }

      el("applyConfig").addEventListener("click", async () => {
        el("configStatus").textContent = "Guardando y reiniciando...";
        const payload = {
          output: {
            backend: el("outputBackend").value,
            serial: {
              device: el("serialDevice").value,
              baudrate: Number(el("serialBaud").value || 9600),
              parity: el("serialParity").value,
              stopbits: Number(el("serialStopbits").value || 1),
              terminator: el("serialTerminator").value,
            },
          },
        };
        try {
          const save = await fetch("/ui/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          if (!save.ok) throw new Error(await save.text());
          const restart = await fetch("/ui/service/restart", { method: "POST" });
          if (!restart.ok) throw new Error(await restart.text());
          const ok = await waitForHealth();
          el("configStatus").textContent = ok
            ? "Cambios aplicados y servicio listo."
            : "Reinicio solicitado. Espera unos segundos y revisa estado.";
          refreshConfig();
        } catch (err) {
          el("configStatus").textContent = `Error aplicando: ${err}`;
        }
      });

      async function loadConfigRaw() {
        try {
          const data = await fetchJson("/ui/config/raw");
          el("configRaw").value = data.raw || "";
          el("configRawStatus").textContent = data.writable
            ? "JSON cargado. Puedes editar y guardar."
            : "Config no editable (permiso).";
        } catch (err) {
          el("configRawStatus").textContent = `Error cargando JSON: ${err}`;
        }
      }

      el("loadConfigRaw").addEventListener("click", () => {
        loadConfigRaw();
      });

      el("saveConfigRaw").addEventListener("click", async () => {
        const raw = el("configRaw").value || "";
        try {
          const res = await fetch("/ui/config/raw", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ raw }),
          });
          if (!res.ok) throw new Error(await res.text());
          el("configRawStatus").textContent = "JSON guardado. Reinicia el servicio para aplicar.";
          refreshConfig();
          refreshMapping();
        } catch (err) {
          el("configRawStatus").textContent = `Error guardando JSON: ${err}`;
        }
      });

      async function runPredict(file, target) {
        try {
          target.textContent = "processing...";
          const form = new FormData();
          form.append("file", file);
          const res = await fetch("/ui/predict", { method: "POST", body: form });
          const text = await res.text();
          if (!res.ok) throw new Error(text || `HTTP ${res.status}`);
          const payload = JSON.parse(text);
          target.textContent = pretty(payload);
          updateBestGuess(payload.best_guess);
          renderTopList(payload.aggregate_top_k || []);
        } catch (err) {
          target.textContent = `error: ${err}`;
          updateBestGuess(null);
          renderTopList([]);
        }
      }

      el("fileInput").addEventListener("change", () => {
        const file = el("fileInput").files[0];
        activeMode = "file";
        stopCamera();
        if (!file) {
          el("previewLabel").textContent = "Sin archivo";
          resetPreview();
          return;
        }
        el("previewLabel").textContent = file.name || "archivo seleccionado";
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = URL.createObjectURL(file);
        const kind = guessFileKind(file);
        if (kind.isImage) {
          el("previewImage").src = previewUrl;
          showPreview("image");
        } else if (kind.isVideo) {
          el("previewVideo").src = previewUrl;
          showPreview("video");
          el("previewVideo").play().catch(() => {});
        } else {
          el("previewLabel").textContent = "Tipo de archivo no soportado";
          resetPreview();
          return;
        }
        runPredict(file, el("predict"));
      });

      el("cameraAction").addEventListener("click", async () => {
        const img = el("cameraStream");
        if (cameraActive && img && img.src && img.naturalWidth) {
          captureCamera();
          return;
        }
        await startCameraStream();
      });

      el("cameraStop").addEventListener("click", () => {
        stopCamera();
        resetPreview();
      });

      el("clearButton").addEventListener("click", () => {
        resetPreview();
        resetResults();
        stopCamera();
      });

      el("refreshCameras").addEventListener("click", () => {
        loadCameras();
      });

      el("cameraSelect").addEventListener("change", () => {
        activeCamera = el("cameraSelect").value;
      });

      el("openRecognition").addEventListener("click", () => {
        setScreen("recognition");
      });

      el("openEtpos").addEventListener("click", () => {
        setScreen("etpos");
      });

      el("backHomeFromRecognition").addEventListener("click", () => {
        setScreen("home");
      });

      el("backHomeFromEtpos").addEventListener("click", () => {
        setScreen("home");
      });

      resetPreview();
      resetResults();
      loadCameras();
      setCameraUi(false);
      bindCameraStreamEvents();
      refreshConfig();
      refreshMapping();
      loadConfigRaw();
      setScreen("home");
      refreshStatus();
      setInterval(refreshStatus, 5000);
    </script>
  </body>
</html>"""


def _list_camera_devices() -> List[Dict[str, str]]:
    devices: List[Dict[str, str]] = []
    for path in sorted(glob.glob("/dev/video*")):
        try:
            mode = os.stat(path).st_mode
        except OSError:
            continue
        if not stat.S_ISCHR(mode):
            continue
        base = os.path.basename(path)
        name_path = os.path.join("/sys/class/video4linux", base, "name")
        name = None
        try:
            with open(name_path, "r", encoding="utf-8") as handle:
                name = handle.read().strip()
        except OSError:
            name = None
        devices.append({"path": path, "name": name or path})
    return devices


def _resolve_camera_device(device: str) -> str | int:
    device = (device or "").strip()
    if not device:
        return "/dev/video0"
    if device.isdigit():
        return int(device)
    if device.startswith("video") and device[5:].isdigit():
        return f"/dev/{device}"
    if device.startswith("/dev/video"):
        return device
    raise ValueError("Invalid camera device")


def _frame_id_from_bytes(payload: bytes) -> int:
    digest = hashlib.sha256(payload).hexdigest()
    return int(digest[:8], 16)


def _map_probs(state: RuntimeState, probs: List[ClassProb]) -> List[Dict[str, Optional[float]]]:
    mapped: List[Dict[str, Optional[float]]] = []
    mapper = state.mapper
    for item in probs:
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


def _map_top_k(state: RuntimeState, result: InferenceResult) -> List[Dict[str, Optional[float]]]:
    return _map_probs(state, result.top_k)


def _get_config(state: RuntimeState) -> AppConfig:
    return state.config or AppConfig()


def _get_config_path(state: RuntimeState) -> Optional[str]:
    return state.config_path or os.getenv("SCALE_VISION_CONFIG")


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
        labels = getattr(state.inference, "labels", None)
        labels_count = len(labels) if labels else 0
        active_backend = state.inference.name if state.inference else config.inference.backend
        return {
            "output_backend": config.output.backend,
            "serial_device": serial_device,
            "serial_exists": serial_exists,
            "serial_writable": serial_writable,
            "kill_switch_active": os.path.exists(kill_switch),
            "inference_backend": active_backend,
            "configured_backend": config.inference.backend,
            "labels_count": labels_count,
            "mapping_count": len(config.mapping.classes),
            "http_bind": config.http.bind,
            "http_port": config.http.port,
            "normalize_width": config.ingestion.normalize.width,
            "normalize_height": config.ingestion.normalize.height,
        }

    @app.get("/ui/mapping")
    def ui_mapping() -> dict:
        config = _get_config(state)
        items = [
            {
                "class_id": class_id,
                "code_type": entry.code_type,
                "code": entry.code,
                "aliases": entry.aliases,
                "disabled": entry.disabled,
            }
            for class_id, entry in sorted(config.mapping.classes.items())
        ]
        return {"items": items}

    @app.get("/ui/config")
    def ui_config() -> dict:
        config = _get_config(state)
        config_path = _get_config_path(state)
        writable = bool(config_path and os.path.exists(config_path) and os.access(config_path, os.W_OK))
        return {
            "output": {
                "backend": config.output.backend,
                "serial": {
                    "device": config.output.serial.device,
                    "baudrate": config.output.serial.baudrate,
                    "parity": config.output.serial.parity,
                    "stopbits": config.output.serial.stopbits,
                    "terminator": config.output.serial.terminator,
                },
            },
            "writable": writable,
            "config_path": config_path,
        }

    @app.get("/ui/config/raw")
    def ui_config_raw() -> dict:
        config_path = _get_config_path(state)
        if not config_path or not os.path.exists(config_path):
            raise HTTPException(status_code=400, detail="Config path unavailable")
        writable = os.access(config_path, os.W_OK)
        with open(config_path, "r", encoding="utf-8") as handle:
            raw = handle.read()
        return {"raw": raw, "writable": bool(writable), "config_path": config_path}

    @app.post("/ui/config/raw")
    def ui_config_raw_update(payload: dict = Body(...)) -> dict:
        config_path = _get_config_path(state)
        if not config_path or not os.path.exists(config_path):
            raise HTTPException(status_code=400, detail="Config path unavailable")
        if not os.access(config_path, os.W_OK):
            raise HTTPException(status_code=403, detail="Config not writable")
        if not isinstance(payload, dict) or "raw" not in payload:
            raise HTTPException(status_code=400, detail="Missing raw config")
        raw = payload.get("raw", "")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc
        try:
            _ = AppConfig.model_validate(data)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Config validation failed: {exc}") from exc
        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=False)
            handle.write("\n")
        state.config = AppConfig.model_validate(data)
        return {"ok": True}

    @app.post("/ui/config")
    def ui_config_update(payload: dict = Body(...)) -> dict:
        config_path = _get_config_path(state)
        if not config_path or not os.path.exists(config_path):
            raise HTTPException(status_code=400, detail="Config path unavailable")
        if not os.access(config_path, os.W_OK):
            raise HTTPException(status_code=403, detail="Config not writable")
        output = payload.get("output") if isinstance(payload, dict) else None
        if not output or not isinstance(output, dict):
            raise HTTPException(status_code=400, detail="Missing output config")
        backend = output.get("backend", "test")
        if backend not in {"test", "serial", "hid"}:
            raise HTTPException(status_code=400, detail="Invalid output backend")
        serial = output.get("serial", {})
        if not isinstance(serial, dict):
            raise HTTPException(status_code=400, detail="Invalid serial config")
        try:
            baudrate = int(serial.get("baudrate", 9600))
            stopbits = int(serial.get("stopbits", 1))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid serial numeric values") from exc
        parity = serial.get("parity", "none")
        if parity not in {"none", "even", "odd"}:
            raise HTTPException(status_code=400, detail="Invalid parity")
        terminator = serial.get("terminator", "\\r\\n")
        device = serial.get("device", "/dev/ttyUSB0")

        with open(config_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        data.setdefault("output", {})
        data["output"]["backend"] = backend
        data["output"].setdefault("serial", {})
        data["output"]["serial"].update(
            {
                "device": device,
                "baudrate": baudrate,
                "parity": parity,
                "stopbits": stopbits,
                "terminator": terminator,
            }
        )
        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=False)
            handle.write("\n")
        try:
            state.config = AppConfig.model_validate(data)
        except Exception:
            pass
        return {"ok": True}

    @app.post("/ui/service/restart")
    def ui_service_restart() -> dict:
        cmd = ["/bin/systemctl", "restart", "scale-vision.service"]
        if os.geteuid() != 0:
            cmd = ["/usr/bin/sudo", "-n"] + cmd
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"ok": True}

    @app.get("/ui/camera/devices")
    def ui_camera_devices() -> dict:
        return {"devices": _list_camera_devices()}

    @app.get("/ui/camera/frame")
    def ui_camera_frame(device: str = "/dev/video0") -> Response:
        try:
            resolved = _resolve_camera_device(device)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        cap = cv2.VideoCapture(resolved)
        if cap is None or not cap.isOpened():
            raise HTTPException(status_code=503, detail=f"Unable to open camera {device}")
        ok, frame = cap.read()
        cap.release()
        if not ok or frame is None:
            raise HTTPException(status_code=503, detail="Unable to read from camera")
        success, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not success:
            raise HTTPException(status_code=500, detail="Failed to encode frame")
        return Response(content=jpg.tobytes(), media_type="image/jpeg")

    @app.get("/ui/camera/stream")
    def ui_camera_stream(device: str = "/dev/video0") -> StreamingResponse:
        try:
            resolved = _resolve_camera_device(device)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        cap = cv2.VideoCapture(resolved)
        if cap is None or not cap.isOpened():
            raise HTTPException(status_code=503, detail=f"Unable to open camera {device}")

        def _generate():
            target_fps = 12.0
            min_interval = 1.0 / target_fps
            last_ts = 0.0
            try:
                while True:
                    now = time.monotonic()
                    if last_ts and now - last_ts < min_interval:
                        time.sleep(min_interval - (now - last_ts))
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        break
                    success, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                    if not success:
                        continue
                    last_ts = time.monotonic()
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + jpg.tobytes()
                        + b"\r\n"
                    )
            finally:
                cap.release()

        return StreamingResponse(_generate(), media_type="multipart/x-mixed-replace; boundary=frame")

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
        quality_ok_frames = 0
        score_accum: Dict[str, float] = {}
        processed = 0

        def _accumulate(result: InferenceResult, quality_ok: bool) -> None:
            nonlocal quality_ok_frames
            for item in result.top_k:
                score_accum[item.class_id] = score_accum.get(item.class_id, 0.0) + item.prob
            if quality_ok:
                quality_ok_frames += 1

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
            _accumulate(last_result, last_quality_ok)
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
                    _accumulate(last_result, last_quality_ok)
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

        aggregate_top_k: List[ClassProb] = []
        if score_accum:
            avg_scores = [(class_id, total / processed) for class_id, total in score_accum.items()]
            aggregate_top_k = [
                ClassProb(class_id=class_id, prob=prob)
                for class_id, prob in sorted(avg_scores, key=lambda item: item[1], reverse=True)[
                    : config.inference.top_k
                ]
            ]

        decision_payload = decision.__dict__ if decision else {}
        if decision and decision.class_id and state.mapper is not None:
            map_result = state.mapper.map_class(decision.class_id)
            decision_payload["code"] = map_result.code
            decision_payload["mapping_reason"] = map_result.reason

        aggregate_payload = _map_probs(state, aggregate_top_k)
        best_guess = aggregate_payload[0] if aggregate_payload else None

        return {
            "mode": "video" if is_video else "image",
            "frames_processed": processed,
            "quality_ok": last_quality_ok,
            "quality_ok_frames": quality_ok_frames,
            "top_k": _map_top_k(state, last_result),
            "aggregate_top_k": aggregate_payload,
            "best_guess": best_guess,
            "decision": decision_payload,
        }

    return app
