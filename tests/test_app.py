"""Tests for the rebuilt 2DayMovie site and its data files."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app import app as flask_app

ROOT = Path(__file__).resolve().parent.parent
CATALOG = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))["items"]
TRAILERS = json.loads((ROOT / "data" / "trailers.json").read_text(encoding="utf-8"))["items"]
CHANNELS = json.loads((ROOT / "scripts" / "channels.json").read_text(encoding="utf-8"))
YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
SECTIONS = {"movies", "series", "kids", "cartoons", "ai", "wildlife"}


@pytest.fixture()
def client():
    flask_app.config.update(TESTING=True)
    return flask_app.test_client()


def test_health_ready_metrics(client):
    assert client.get("/healthz").get_json() == {"status": "ok"}
    ready = client.get("/readyz").get_json()
    assert ready["status"] == "ready" and ready["videos"] == len(CATALOG)
    assert client.get("/metrics").status_code == 200


def test_home_page_has_navigation_hero_search_and_player(client):
    html = client.get("/").get_data(as_text=True)
    for anchor in ("#trailers", "#movies", "#series", "#kids", "#cartoons", "#ai", "#wildlife"):
        assert f'href="{anchor}"' in html
    for element_id in ("heroTrack", "heroPrev", "heroNext", "heroDots", "searchInput", "player"):
        assert f'id="{element_id}"' in html
    for asset in ("static/js/app.js", "static/js/hero.js", "static/js/search.js", "static/css/app.css"):
        assert asset in html


def test_static_assets_and_public_data_served(client):
    for asset in ("js/app.js", "js/hero.js", "js/search.js", "css/app.css"):
        assert client.get(f"/static/{asset}").status_code == 200
    assert client.get("/data/catalog.json").status_code == 200
    assert client.get("/data/trailers.json").status_code == 200
    assert client.get("/data/catalog_sources.json").status_code == 404


def test_legacy_urls_redirect_home(client):
    for path in ("/library", "/movies", "/watch/123", "/series/watch/9", "/upcoming"):
        resp = client.get(path)
        assert resp.status_code == 301 and resp.headers["Location"].endswith("/")
    assert client.get("/nope-not-here").status_code == 404


def test_catalog_schema_and_ids():
    ids = [v["id"] for v in CATALOG]
    assert len(ids) == len(set(ids)), "duplicate videos"
    for v in CATALOG:
        assert set(v) == {"id", "title", "type", "genres", "duration", "thumbnail"}, "public schema only"
        assert YT_ID.match(v["id"]) and v["type"] in SECTIONS and v["title"].strip()
        assert v["genres"] and all(isinstance(g, str) and g for g in v["genres"])
        assert isinstance(v["duration"], int) and v["duration"] > 0
        assert v["thumbnail"].startswith("https://i.ytimg.com/vi/" + v["id"])


def test_long_form_rules():
    for v in CATALOG:
        if v["type"] == "movies":
            assert v["duration"] >= 40 * 60, v
        if v["type"] == "wildlife":
            assert v["duration"] >= 20 * 60, v


def test_sections_present():
    assert {v["type"] for v in CATALOG} >= {"movies", "series", "wildlife", "ai"}


def test_no_channel_names_shown_to_users(client):
    public = client.get("/").get_data(as_text=True) + json.dumps(CATALOG, ensure_ascii=False)
    for js in ("app.js", "hero.js", "search.js"):
        public += (ROOT / "static" / "js" / js).read_text(encoding="utf-8")
    labels = {g for v in CATALOG for g in v["genres"]}
    for ch in CHANNELS:
        assert ch["name"].split(" — ")[0] not in labels, f"row named after a channel: {ch['name']}"
    assert "youtube.com/@" not in public and "/channel/UC" not in public


def test_trailers_upcoming_and_include_avengers_doomsday():
    assert TRAILERS, "hero needs trailers"
    assert TRAILERS[0]["title"] == "Avengers: Doomsday"
    for t in TRAILERS:
        assert set(t) == {"title", "release_date", "youtube_id", "start", "end"}
        assert YT_ID.match(t["youtube_id"]) and t["release_date"] >= "2026-01-01"
        assert 0 <= t["start"] < t["end"]
        assert t["youtube_id"] not in {v["id"] for v in CATALOG}
