"""Checks for the areas in qa/security-scope.md (GRC, Cloud, IAM)."""
from __future__ import annotations

import datetime as dt
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SECRET = re.compile(
    r"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|AIza[0-9A-Za-z_-]{35}"
    r"|(?i:(?:password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"]?[A-Za-z0-9/+_\-]{12,})"
)
PLACEHOLDERS = ("your_tmdb_v3_api_key_here", "ci-validation-only", "/etc/prometheus/metrics_token")


# ---------- GRC ----------
def test_security_txt_is_rfc9116_and_not_expired(client):
    resp = client.get("/.well-known/security.txt")
    assert resp.status_code == 200 and resp.mimetype == "text/plain"
    text = resp.get_data(as_text=True)
    assert re.search(r"^Contact: mailto:\S+@\S+$", text, re.M)
    m = re.search(r"^Expires: (\S+)$", text, re.M)
    expires = dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    assert now < expires <= now + dt.timedelta(days=400), "Expires must be in the future and under ~a year out"
    for out in ("", "docs/"):
        assert (ROOT / out / ".well-known/security.txt").read_text() == (ROOT / ".well-known/security.txt").read_text()


def test_robots_allows_site_and_hides_operator_endpoints(client):
    text = client.get("/robots.txt").get_data(as_text=True)
    assert "User-agent: *" in text and "Allow: /" in text
    for p in ("/metrics", "/healthz", "/readyz"):
        assert f"Disallow: {p}" in text
    assert not re.search(r"^Disallow: /\s*$", text, re.M), "site must stay crawlable"


def test_privacy_and_rights_notes_are_on_the_page(client):
    html = client.get("/").get_data(as_text=True)
    assert 'id="privacy"' in html
    for phrase in ("no accounts", "no tracking cookies of its own", "sets no cookies", "youtube-nocookie.com",
                   "YouTube still sets its own cookies", "localStorage", "tdm.hero.v1",
                   "rehosted", "YouTube's Terms of Service"):
        assert phrase in html, phrase


def test_site_sets_no_cookies(client):
    for path in ("/", "/data/catalog.json", "/static/js/app.js", "/nope", "/robots.txt"):
        assert "Set-Cookie" not in client.get(path).headers, path


def test_local_storage_holds_only_ui_preferences():
    js = "".join((ROOT / "static/js" / f).read_text() for f in ("app.js", "hero.js", "search.js"))
    assert "document.cookie" not in js and "sessionStorage" not in js
    keys = set(re.findall(r'STORE_KEY = "([^"]+)"', js))
    assert keys == {"tdm.hero.v1"}
    assert re.findall(r"localStorage\.\w+\(([^,)]+)", js) == ["STORE_KEY", "STORE_KEY"]
    saved = set(re.findall(r"prefs\.save\(\{\s*(\w+)", js))
    assert saved <= {"sound", "volume", "brightness", "size"}, saved


def test_third_party_notices_cover_bundled_icons():
    text = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
    assert "Material Design Icons" in text and "Apache License 2.0" in text
    static = [p for p in (ROOT / "static").rglob("*") if p.suffix in {".js", ".css"}]
    assert sorted(p.name for p in static) == ["404.css", "app.css", "app.js", "hero.js", "search.js"], \
        "new static JS/CSS must be listed in THIRD_PARTY_NOTICES.md if third-party"


# ---------- Cloud ----------
def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        pytest.skip("not a git checkout")
    return [ROOT / f for f in out.stdout.splitlines()]


def test_no_secrets_in_tracked_files():
    hits = []
    for path in tracked_files():
        if not path.is_file() or path.suffix in {".png", ".jpg", ".ico", ".webp"}:
            continue
        for m in SECRET.finditer(path.read_text(encoding="utf-8", errors="ignore")):
            if not any(p in m.group(0) for p in PLACEHOLDERS) and not path.name.startswith("test_"):
                hits.append(path.relative_to(ROOT).as_posix())
    assert not hits, f"possible secrets in: {sorted(set(hits))}"


def test_private_files_are_untracked_and_ignored():
    names = {p.relative_to(ROOT).as_posix() for p in tracked_files()}
    for f in ("scripts/channels.json", "scripts/channel_resolution.json", "data/catalog_sources.json",
              "deploy/monitoring/metrics_token", ".env"):
        assert f not in names, f
    dockerignore = (ROOT / ".dockerignore").read_text().split()
    for f in (".env", "tests", "scripts/channels.json", "deploy/monitoring/metrics_token", "data/catalog_sources.json"):
        assert f in dockerignore, f


def test_render_and_compose_keep_secrets_out():
    render = (ROOT / "render.yaml").read_text()
    assert re.search(r"key: METRICS_TOKEN\n\s+sync: false", render)
    assert "TMDB" not in render
    compose = (ROOT / "docker-compose.yml").read_text()
    assert "${GRAFANA_ADMIN_PASSWORD:?" in compose
    assert not re.search(r"GF_SECURITY_ADMIN_PASSWORD:\s*\"?admin", compose)


def test_docker_image_is_non_root_and_minimal():
    df = (ROOT / "Dockerfile").read_text()
    assert re.search(r"^USER appuser$", df, re.M) and "--uid 10001" in df
    assert "apt-get install" not in df, "no extra OS packages"
    assert "pytest" not in (ROOT / "requirements.txt").read_text(), "test tools stay out of the image"
    assert "pytest" in (ROOT / "requirements-dev.txt").read_text()


def test_workflows_are_least_privilege_and_pinned():
    for wf in (ROOT / ".github/workflows").glob("*.yml"):
        text = wf.read_text()
        top = text.split("\njobs:", 1)[0]
        assert re.search(r"^permissions:", top, re.M), f"{wf.name}: top-level permissions"
        assert "write" not in top, f"{wf.name}: no write scopes at the top level"
        for use in re.findall(r"uses:\s*(\S+)", text):
            assert re.search(r"@[0-9a-f]{40}$", use), f"{wf.name}: {use} not pinned to a SHA"
    pages = (ROOT / ".github/workflows/pages.yml").read_text()
    build, deploy = pages.split("\n  deploy:", 1)
    assert "pages: write" not in build and "id-token: write" not in build
    assert "pages: write" in deploy and "id-token: write" in deploy


# ---------- IAM ----------
def test_no_default_credentials_in_docs_or_config():
    for rel in ("DEVOPS.md", "README.md", "docker-compose.yml", ".env.example", "deploy"):
        base = ROOT / rel
        files = [base] if base.is_file() else [p for p in base.rglob("*") if p.is_file()]
        for f in files:
            text = f.read_text(errors="ignore")
            assert not re.search(r"admin\s*/\s*admin|password\s*[:=]\s*\"?admin\b", text, re.I), f.name


def test_metrics_token_must_be_strong(client, monkeypatch):
    from app import METRICS_TOKEN_MIN
    assert METRICS_TOKEN_MIN >= 32
    short = "x" * (METRICS_TOKEN_MIN - 1)
    monkeypatch.setenv("METRICS_TOKEN", short)
    assert client.get("/metrics", headers={"Authorization": f"Bearer {short}"}).status_code == 404
    good = "y" * METRICS_TOKEN_MIN
    monkeypatch.setenv("METRICS_TOKEN", good)
    assert client.get("/metrics", headers={"Authorization": f"Bearer {good}"}).status_code == 200
