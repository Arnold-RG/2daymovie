"""Security headers. Present headers are asserted; missing ones are xfail until Forge adds them."""
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


@pytest.mark.xfail(reason="Forge has not added Content-Security-Policy yet (see qa/security-review.md)", strict=False)
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


@pytest.mark.xfail(reason="Forge has not added Strict-Transport-Security yet (see qa/security-review.md)", strict=False)
def test_hsts_present(client):
    resp = client.get("/")
    hsts = resp.headers.get("Strict-Transport-Security", "")
    assert hsts, "Strict-Transport-Security is missing"
    assert "max-age=" in hsts.lower()


@pytest.mark.xfail(reason="Forge has not added Permissions-Policy yet (see qa/security-review.md)", strict=False)
def test_permissions_policy_present(client):
    resp = client.get("/")
    value = resp.headers.get("Permissions-Policy", "")
    assert value, "Permissions-Policy is missing"


@pytest.mark.xfail(reason="Forge has not added frame-ancestors / X-Frame-Options yet (see qa/security-review.md)", strict=False)
def test_clickjacking_protection_present(client):
    resp = client.get("/")
    csp = resp.headers.get("Content-Security-Policy", "")
    xfo = resp.headers.get("X-Frame-Options", "")
    assert "frame-ancestors" in csp or xfo.upper() in {"DENY", "SAMEORIGIN"}
