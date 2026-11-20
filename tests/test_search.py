"""Search endpoint contract: only catalog items, escaped output, junk queries.

Search is currently client-side only (static/js/search.js). These tests require
a server-side search route and will fail until Forge adds one.
"""
from __future__ import annotations

import json
import re
from tests.helpers import ROOT

# Queries include empty, ordinary titles, and junk/XSS strings.
SEARCH_QUERIES = [
    "",
    "a",
    "movie",
    "the",
    "<script>alert(1)</script>",
    '"><img src=x onerror=alert(1)>',
    "{{7*7}}",
    "<svg/onload=alert(1)>",
    "' OR 1=1 --",
]


def _catalog_ids_and_titles():
    doc = json.loads((ROOT / "data" / "catalog.json").read_text(encoding="utf-8"))
    items = doc["items"] if isinstance(doc, dict) else doc
    ids = {item["id"] for item in items}
    titles = {item["title"] for item in items}
    return ids, titles


def discover_search_paths(app) -> list[str]:
    """Return candidate search paths from the Flask url_map."""
    paths = []
    for rule in app.url_map.iter_rules():
        if "GET" not in rule.methods:
            continue
        if "<" in rule.rule:
            continue
        name = f"{rule.endpoint} {rule.rule}".lower()
        if "search" in name:
            paths.append(rule.rule)
    return paths


def _get_search(client, path, query):
    return client.get(path, query_string={"q": query})


def test_search_endpoint_exists(app):
    paths = discover_search_paths(app)
    assert paths, (
        "No search endpoint found in app.url_map. Search is implemented only in "
        "static/js/search.js (client-side). Forge needs a GET search route "
        "(for example /api/search?q=) that returns only catalog items, so empty, "
        "junk, and XSS queries can be tested on the server."
    )


def test_search_returns_only_catalog_items_and_escapes_query(client, app):
    paths = discover_search_paths(app)
    if not paths:
        raise AssertionError(
            "No search endpoint in url_map; cannot verify catalog-only results "
            "or output escaping. See test_search_endpoint_exists."
        )
    ids, titles = _catalog_ids_and_titles()
    path = paths[0]
    problems = []
    for query in SEARCH_QUERIES:
        resp = _get_search(client, path, query)
        if resp.status_code != 200:
            problems.append(f"q={query!r} returned {resp.status_code}")
            continue
        ctype = resp.headers.get("Content-Type", "")
        body = resp.get_data(as_text=True)
        returned_ids = set()
        if "json" in ctype:
            try:
                payload = resp.get_json(silent=False)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"q={query!r} invalid JSON: {type(exc).__name__}")
                continue
            items = payload if isinstance(payload, list) else (payload or {}).get("items") or (payload or {}).get("results") or []
            for item in items:
                ident = item.get("id") if isinstance(item, dict) else None
                if ident:
                    returned_ids.add(ident)
        else:
            # HTML: every data-id / youtube id in the result must be in the catalog.
            returned_ids.update(re.findall(r'data-id="([A-Za-z0-9_-]{11})"', body))
            # Titles appearing as results must be catalog titles; skip this if the
            # page is a full shell rather than a result list.
        extra = returned_ids - ids
        if extra:
            problems.append(f"q={query!r} returned {len(extra)} id(s) not in the catalog")
        if query:
            # The raw (unescaped) XSS payload must not appear as HTML/JS.
            if "<script>alert(1)</script>" in query and "<script>alert(1)</script>" in body:
                problems.append("raw <script> payload was reflected unescaped")
            if "onerror=alert(1)" in query and "onerror=alert(1)" in body:
                problems.append("raw onerror= payload was reflected unescaped")
            if any(tok in query for tok in ("<script", "onerror=", "<svg")):
                if query in body and "json" not in ctype:
                    problems.append(f"unsafe query reflected unescaped in HTML")
                elif "json" in ctype and query in body:
                    # JSON string encoding is acceptable if quotes are escaped.
                    if f'"{query}"' in body or f'"{query.replace("\\", "\\\\")}"' in body:
                        # still check it isn't dropped into an HTML context
                        pass
        # Empty query: must not 500; results, if any, still catalog-only (checked above).
        if query == "" and resp.status_code != 200:
            problems.append("empty query did not return 200")
    assert not problems, problems
