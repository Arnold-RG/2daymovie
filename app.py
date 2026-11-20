"""2DayMovie web app.

templates/index.html is the app shell; static/ holds CSS and JS and data/ the
catalog. scripts/export_site.py renders the same page to /index.html (served by
the Render static site) and /docs (GitHub Pages), so all three stay in sync.
Flask adds health, readiness and Prometheus metrics for the Docker service and
redirects every legacy URL from the old site to the new home page.
"""
from __future__ import annotations

import hmac
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, abort, g, jsonify, redirect, render_template, request, send_from_directory
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

load_dotenv()

ROOT = Path(__file__).resolve().parent
PUBLIC_DATA = {"catalog.json", "trailers.json"}  # catalog_sources.json stays internal

REQUESTS = Counter("twodaymovie_http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
LATENCY = Histogram("twodaymovie_http_request_duration_seconds", "HTTP request latency", ["endpoint"])

YT_NOCOOKIE = "https://www.youtube-nocookie.com"
# The IFrame API loader and its widget script come from www.youtube.com; every
# player frame is youtube-nocookie.com and thumbnails come from i.ytimg.com.
CSP_DIRECTIVES = {
    "default-src": "'self'",
    "script-src": "'self' https://www.youtube.com",
    "style-src": "'self'",
    "img-src": "'self' data: https://i.ytimg.com",
    "connect-src": "'self'",
    "frame-src": YT_NOCOOKIE,
    "media-src": "'none'",
    "object-src": "'none'",
    "base-uri": "'self'",
    "form-action": "'self'",
    "frame-ancestors": "'none'",
}
CSP = "; ".join(f"{k} {v}" for k, v in CSP_DIRECTIVES.items())
# <meta> CSP for hosts that cannot send headers (GitHub Pages); frame-ancestors is header-only.
CSP_META = "; ".join(f"{k} {v}" for k, v in CSP_DIRECTIVES.items() if k != "frame-ancestors")
_YT = f'(self "{YT_NOCOOKIE}")'
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Permissions-Policy": (
        f"autoplay={_YT}, fullscreen={_YT}, encrypted-media={_YT}, picture-in-picture={_YT}, "
        "camera=(), microphone=(), geolocation=(), payment=(), usb=()"
    ),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
}

LEGACY_PREFIXES = ("/library", "/movies", "/movie", "/series", "/watch", "/browse", "/genre", "/year",
                   "/search", "/upcoming", "/categories", "/reviews", "/about", "/api/reviews")


def load_catalog() -> dict:
    return json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))


def _items(doc) -> list:
    return doc if isinstance(doc, list) else doc.get("items", [])


def load_trailers() -> dict:
    return json.loads((ROOT / "data" / "trailers.json").read_text(encoding="utf-8"))


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")

    @app.before_request
    def _start_timer():
        g.start = time.perf_counter()

    @app.after_request
    def _record(resp):
        endpoint = request.endpoint or "unknown"
        REQUESTS.labels(request.method, endpoint, resp.status_code).inc()
        if hasattr(g, "start"):
            LATENCY.labels(endpoint).observe(time.perf_counter() - g.start)
        for name, value in SECURITY_HEADERS.items():
            resp.headers.setdefault(name, value)
        return resp

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    @app.get("/readyz")
    def readyz():
        try:
            videos = len(_items(load_catalog()))
            trailers = len(_items(load_trailers()))
        except (OSError, ValueError, KeyError):
            return jsonify(status="not-ready"), 503
        return jsonify(status="ready", videos=videos, trailers=trailers)

    @app.get("/metrics")
    def metrics():
        # Private: only answers with "Authorization: Bearer <METRICS_TOKEN>".
        # With no token configured the endpoint does not exist.
        token = os.getenv("METRICS_TOKEN", "")
        sent = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        if not token or not hmac.compare_digest(sent.encode(), token.encode()):
            abort(404)
        resp = Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/")
    def index():
        return render_template("index.html", base="", csp_meta=CSP_META)

    @app.get("/data/<name>")
    def data(name: str):
        if name not in PUBLIC_DATA:
            abort(404)
        return send_from_directory(ROOT / "data", name, max_age=300)

    @app.get("/robots.txt")
    def robots():
        return send_from_directory(ROOT, "robots.txt", mimetype="text/plain")


    @app.errorhandler(404)
    def not_found(_err):
        path = request.path.rstrip("/")
        if path.startswith(LEGACY_PREFIXES):
            return redirect("/", code=301)
        return render_template("404.html", base="/"), 404

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=os.getenv("FLASK_DEBUG") == "1")
