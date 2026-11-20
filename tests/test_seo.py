"""SEO launch checklist: robots, sitemap, per-page titles and descriptions."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import seo
from app import load_catalog

ROOT = Path(__file__).resolve().parent.parent
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
PAGES = seo.pages(load_catalog())


def test_robots_welcomes_ai_and_search_crawlers_and_points_to_sitemap(client):
    text = client.get("/robots.txt").get_data(as_text=True)
    for bot in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "Bingbot"):
        assert f"User-agent: {bot}" in text, bot
    assert not re.search(r"^Disallow: /\s*$", text, re.M), "nothing may block the whole site"
    assert re.search(r"^Sitemap: https://\S+/sitemap\.xml$", text, re.M)
    for f in ("robots.txt", "docs/robots.txt"):
        assert "Sitemap: " in (ROOT / f).read_text() and "GPTBot" in (ROOT / f).read_text()


def test_sitemap_lists_every_page_section_and_genre(client):
    for xml in (client.get("/sitemap.xml").data, (ROOT / "sitemap.xml").read_bytes(), (ROOT / "docs/sitemap.xml").read_bytes()):
        locs = [n.text for n in ET.fromstring(xml).findall("s:url/s:loc", NS)]
        paths = [re.sub(r"^https://[^/]+/(2daymovie/)?", "", u) for u in locs]
        assert paths == [seo.page_path(p) for p in PAGES]
    slugs = {p["slug"] for p in PAGES}
    for s in ("trailers", "movies", "series", "kids", "cartoons", "ai", "wildlife", "genres", "genre-drama", "genre-musical"):
        assert s in slugs, s


def test_titles_and_descriptions_are_unique_and_descriptive():
    titles = [p["title"] for p in PAGES]
    descs = [p["description"] for p in PAGES]
    assert len(set(titles)) == len(titles) and len(set(descs)) == len(descs)
    for p in PAGES:
        assert 25 <= len(p["title"]) <= 90, p["title"]
        assert 70 <= len(p["description"]) <= 170, p["description"]
        assert "2DayMovie" in p["title"]


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p["slug"] or "home")
def test_each_page_renders_its_own_meta(client, page):
    path = "/" + seo.page_path(page)
    html = client.get(path).get_data(as_text=True)
    from html import unescape
    assert unescape(re.search(r"<title>([^<]+)</title>", html).group(1)) == page["title"]
    assert unescape(re.search(r'<meta name="description" content="([^"]+)"', html).group(1)) == page["description"]
    assert f'<link rel="canonical" href="{seo.SITE_URL}{seo.page_path(page)}">' in html
    if page["anchor"]:
        assert f'data-start="{page["anchor"]}"' in html
        assert 'href="../../static/css/app.css"' in html and 'data-base="../../"' in html
    exported = ROOT / seo.page_path(page) / "index.html"
    assert exported.read_text(encoding="utf-8") == html, "export is stale: run scripts/export_site.py"


def test_unknown_explore_page_is_404(client):
    assert client.get("/explore/nope/").status_code == 404


def test_page_ids_match_the_app():
    js = (ROOT / "static/js/app.js").read_text()
    assert f"const GENRE_MIN = {seo.GENRE_MIN};" in js
    assert "const GENRES = [" + ", ".join(f'"{g}"' for g in seo.GENRES) + "];" in js
