"""Security headers sent by app.py (and mirrored in render.yaml for the static site)."""
from __future__ import annotations

import pytest


def test_x_content_type_options_nosniff(client):
    resp = client.get("/")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"


def test_referrer_policy_is_set(client):
    resp = client.get("/")
    value = resp.headers.get("Referrer-Policy", "")
    assert value, "Referrer-Policy header is missing"
    assert "origin" in value.lower() or value.lower() in {"no-referrer", "same-origin"}


def test_content_security_policy_present(client):
    resp = client.get("/")
    csp = resp.headers.get("Content-Security-Policy", "")
    assert csp, "Content-Security-Policy is missing"
    assert "frame-src" in csp and "youtube-nocookie.com" in csp
    assert "object-src" in csp and "none" in csp
    assert "base-uri" in csp
    assert "frame-ancestors" in csp
    assert "unsafe-eval" not in csp
    # Recommend no unsafe-inline either; asserted once a policy exists so it cannot regress.
    assert "unsafe-inline" not in csp


def test_hsts_present(client):
    resp = client.get("/")
    hsts = resp.headers.get("Strict-Transport-Security", "")
    assert hsts, "Strict-Transport-Security is missing"
    assert "max-age=" in hsts.lower()


def test_permissions_policy_present(client):
    resp = client.get("/")
    value = resp.headers.get("Permissions-Policy", "")
    assert value, "Permissions-Policy is missing"


def test_clickjacking_protection_present(client):
    resp = client.get("/")
    csp = resp.headers.get("Content-Security-Policy", "")
    xfo = resp.headers.get("X-Frame-Options", "")
    assert "frame-ancestors" in csp or xfo.upper() in {"DENY", "SAMEORIGIN"}


def test_csp_frames_only_youtube_nocookie(client):
    csp = client.get("/").headers["Content-Security-Policy"]
    directives = dict(d.strip().split(" ", 1) for d in csp.split(";") if d.strip())
    assert directives["frame-src"] == "https://www.youtube-nocookie.com"
    assert directives["object-src"] == "'none'" and directives["base-uri"] == "'self'"
    assert directives["frame-ancestors"] == "'none'"


def test_headers_on_static_and_error_responses(client):
    for path in ("/static/js/app.js", "/data/catalog.json", "/does-not-exist"):
        assert "Content-Security-Policy" in client.get(path).headers


def test_no_inline_script_or_style_in_templates():
    import re
    from tests.helpers import ROOT
    for f in (ROOT / "templates").glob("*.html"):
        text = f.read_text(encoding="utf-8")
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", text), f"inline script in {f.name}"
        assert "<style" not in text and " style=" not in text, f"inline style in {f.name}"
