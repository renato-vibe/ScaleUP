from __future__ import annotations

import os
import sys
from typing import Optional

from scale_vision.config.loader import ConfigLoader


def _default_url(config) -> str:
    host = config.http.bind
    if host in ("0.0.0.0", "::", "[::]"):
        host = "127.0.0.1"
    return f"http://{host}:{config.http.port}/"


def _wait_page(base_url: str) -> str:
    base_url = base_url.rstrip("/")
    health_url = f"{base_url}/health"
    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>ScaleUP - Starting</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: #f7fbff;
        --bg-2: #f2f8f5;
        --card: #ffffff;
        --text: #0f172a;
        --muted: #4b5563;
        --accent: #2563eb;
        --ok: #16a34a;
        --warn: #f97316;
        --border: rgba(15, 23, 42, 0.12);
        --shadow: 0 16px 40px rgba(15, 23, 42, 0.12);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "Space Grotesk", "Ubuntu", "DejaVu Sans", sans-serif;
        background: radial-gradient(700px 400px at 15% 0%, #cfe6ff, transparent),
                    radial-gradient(620px 360px at 100% 40%, #c1f0dc, transparent),
                    linear-gradient(180deg, var(--bg), var(--bg-2));
        color: var(--text);
        min-height: 100vh;
        display: grid;
        place-items: center;
      }}
      .card {{
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 28px;
        width: min(520px, 90vw);
        box-shadow: var(--shadow);
      }}
      h1 {{ margin: 0 0 8px; font-size: 24px; }}
      p {{ margin: 0; color: var(--muted); }}
      .status {{
        margin-top: 18px;
        display: inline-flex;
        gap: 8px;
        align-items: center;
        padding: 8px 12px;
        border-radius: 999px;
        font-size: 13px;
        border: 1px solid var(--border);
      }}
      .dot {{
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--warn);
        animation: pulse 1.3s infinite;
      }}
      .hint {{ margin-top: 14px; font-size: 12px; color: var(--muted); }}
      .actions {{ margin-top: 12px; display: flex; gap: 10px; flex-wrap: wrap; }}
      .btn {{
        border: 1px solid var(--border);
        background: #eef6ff;
        color: #1e3a8a;
        padding: 8px 12px;
        border-radius: 10px;
        font-size: 12px;
        cursor: pointer;
      }}
      @keyframes pulse {{
        0% {{ transform: scale(0.9); opacity: 0.6; }}
        50% {{ transform: scale(1.1); opacity: 1; }}
        100% {{ transform: scale(0.9); opacity: 0.6; }}
      }}
    </style>
  </head>
  <body>
    <div class=\"card\">
      <h1>Launching ScaleUP UI</h1>
      <p>Waiting for the local service to respond.</p>
      <div class=\"status\"><span class=\"dot\"></span><span id=\"statusText\">Checking...</span></div>
      <div class=\"hint\" id=\"hint\"></div>
      <div class=\"actions\">
        <button class=\"btn\" id=\"openButton\" type=\"button\">Open UI</button>
        <button class=\"btn\" id=\"retryButton\" type=\"button\">Retry</button>
      </div>
    </div>
    <script>
      const baseUrl = "{base_url}";
      const healthUrl = "{health_url}";
      const statusText = document.getElementById("statusText");
      const hint = document.getElementById("hint");
      const openButton = document.getElementById("openButton");
      const retryButton = document.getElementById("retryButton");

      async function poll() {{
        try {{
          await fetch(healthUrl, {{ cache: "no-store", mode: "no-cors" }});
          statusText.textContent = "Service ready. Loading UI...";
          window.location.href = baseUrl + "/";
          return;
        }} catch (err) {{
          statusText.textContent = "Service not ready";
          hint.textContent = "Make sure the daemon is running: " + healthUrl;
        }}
        setTimeout(poll, 1500);
      }}
      openButton.addEventListener("click", () => {{
        window.location.href = baseUrl + "/";
      }});
      retryButton.addEventListener("click", () => {{
        poll();
      }});
      poll();
    </script>
  </body>
</html>"""


def launch_app(config_path: str, url: Optional[str] = None) -> int:
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        print("scale-vision ui: no desktop session detected (DISPLAY/WAYLAND_DISPLAY missing)", file=sys.stderr)
        return 2

    dist_packages = "/usr/lib/python3/dist-packages"
    if os.path.isdir(dist_packages) and dist_packages not in sys.path:
        sys.path.append(dist_packages)

    try:
        import webview
    except Exception as exc:
        print("scale-vision ui: pywebview is required (pip install 'scale-vision[desktop]')", file=sys.stderr)
        print(f"pywebview import error: {exc}", file=sys.stderr)
        return 2

    loader = ConfigLoader(config_path)
    config = loader.load().config
    target_url = url or _default_url(config)
    wait_page = _wait_page(target_url)

    webview.create_window("ScaleUP", html=wait_page, width=1200, height=820, resizable=True)
    webview.start(debug=False)
    return 0
