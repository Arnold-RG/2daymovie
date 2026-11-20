"""Search is client-side only (static/js/search.js); there is no server route.

These checks replace the old server-endpoint contract: the matcher is run in
node against the real catalog with ordinary, empty and junk/XSS queries, and the
rendering path is checked statically for HTML sinks.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests.helpers import ROOT

SEARCH_QUERIES = [
    "", "a", "movie", "the", "nollywood", "documentary", "avengers",
    "<script>alert(1)</script>", '"><img src=x onerror=alert(1)>', "{{7*7}}",
    "<svg/onload=alert(1)>", "' OR 1=1 --", "x" * 5000,
]
HTML_SINKS = re.compile(r"\.innerHTML\b|\.outerHTML\b|insertAdjacentHTML|document\.write|\beval\(|new Function\(")
JS = ["app.js", "hero.js", "search.js"]


def test_no_server_search_route(app):
    rules = [r.rule for r in app.url_map.iter_rules() if "search" in r.rule.lower()]
    assert not rules, f"search must stay client-side; found routes {rules}"


def test_frontend_has_no_html_injection_sinks():
    for name in JS:
        text = (ROOT / "static" / "js" / name).read_text(encoding="utf-8")
        assert not HTML_SINKS.search(text), f"{name} uses an HTML injection sink"


def test_search_input_is_bounded():
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'id="searchInput"' in html and 'type="search"' in html
    js = (ROOT / "static" / "js" / "search.js").read_text(encoding="utf-8")
    assert "maxLength = MAX_QUERY" in js


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_search_matcher_returns_only_catalog_items():
    harness = r"""
const fs = require("fs");
global.window = {};
global.document = { addEventListener() {} };
eval(fs.readFileSync(process.argv[1], "utf8"));
const cat = JSON.parse(fs.readFileSync(process.argv[2], "utf8")).items;
const tr = JSON.parse(fs.readFileSync(process.argv[3], "utf8")).items
  .map((x) => ({ id: x.youtube_id, film: x.title, release: x.release_date }));
const qs = JSON.parse(process.argv[4]);
const out = {};
for (const q of qs) out[q] = window.TDM.searchItems(q, cat, tr).map((v) => v.id);
process.stdout.write(JSON.stringify(out));
"""
    res = subprocess.run(
        ["node", "-e", harness, str(ROOT / "static/js/search.js"), str(ROOT / "data/catalog.json"),
         str(ROOT / "data/trailers.json"), json.dumps(SEARCH_QUERIES)],
        capture_output=True, text=True, timeout=60, check=True,
    )
    results = json.loads(res.stdout)
    catalog = json.loads((ROOT / "data/catalog.json").read_text(encoding="utf-8"))["items"]
    trailers = json.loads((ROOT / "data/trailers.json").read_text(encoding="utf-8"))["items"]
    known = {v["id"] for v in catalog} | {t["youtube_id"] for t in trailers}
    for q, ids in results.items():
        assert set(ids) <= known, f"query {q[:30]!r} returned ids outside the catalog"
    assert results[""] == []
    for junk in SEARCH_QUERIES[7:]:
        assert results[junk] == [], f"junk query {junk[:30]!r} matched titles"
    assert results["nollywood"], "row names are searchable"
    assert results["avengers"], "upcoming trailers are searchable"
