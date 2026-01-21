from __future__ import annotations

import json

from fastapi import FastAPI, Response

from scale_vision.state import RuntimeState
from scale_vision.versioning import app_version


def create_app(state: RuntimeState) -> FastAPI:
    app = FastAPI(title="scale-vision", version="0.1.0")

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

    return app
