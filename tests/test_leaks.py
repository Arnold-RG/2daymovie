"""Fail if source-channel names, handles, or /@ links appear in public surfaces.

Denylist values are never included in assertion messages (counts and paths only).
"""
from __future__ import annotations

import re

import pytest

from tests.helpers import (
    DENYLIST_MISSING_MSG,
    count_handle_hits,
    count_link_hits,
    count_name_hits,
    denylist_path,
    html_routes,
    iter_text_files,
    load_denylist,
    read_text,
    ROOT,
)

YT_AT = re.compile(r"youtube\.com/@", re.I)
YT_CHANNEL = re.compile(r"youtube\.com/channel/", re.I)


def _public_text_sources(client, app) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    for path in html_routes(app):
        resp = client.get(path)
        sources.append((f"GET {path} (status {resp.status_code})", resp.get_data(as_text=True)))
    # 404 body is also user-visible HTML
    resp = client.get("/this-path-should-not-exist-qa-404")
    sources.append((f"GET 404 page (status {resp.status_code})", resp.get_data(as_text=True)))
    for folder in (ROOT / "static", ROOT / "templates"):
        for file in iter_text_files(folder):
            sources.append((str(file.relative_to(ROOT)), read_text(file)))
    return sources


def test_denylist_not_in_rendered_html_static_or_templates(client, app):
    deny = load_denylist()
    if deny is None:
        pytest.skip(DENYLIST_MISSING_MSG + f" (looked at {denylist_path()})")
    hits = []
    for label, text in _public_text_sources(client, app):
        n = count_name_hits(text, deny["names"])
        h = count_handle_hits(text, deny["handles"])
        l = count_link_hits(text, deny["links"])
        if n or h or l:
            hits.append(f"{label}: names={n} handles={h} links={l}")
    assert not hits, (
        "Source-channel denylist values appeared in rendered HTML, static/, or "
        f"templates/ ({len(hits)} surface(s): {hits})"
    )


def test_no_youtube_at_or_channel_links_in_html_static_or_templates(client, app):
    hits = []
    for label, text in _public_text_sources(client, app):
        at = len(YT_AT.findall(text))
        ch = len(YT_CHANNEL.findall(text))
        if at or ch:
            hits.append(f"{label}: youtube.com/@={at} youtube.com/channel/={ch}")
    assert not hits, (
        "youtube.com/@ or youtube.com/channel/ links appeared in rendered HTML, "
        f"static/, or templates/ ({hits})"
    )


def test_denylist_not_in_public_catalog_or_trailers():
    """Public JSON is fetched by the client and titles are shown in the UI."""
    deny = load_denylist()
    if deny is None:
        pytest.skip(DENYLIST_MISSING_MSG)
    hits = []
    for name in ("catalog.json", "trailers.json"):
        path = ROOT / "data" / name
        if not path.is_file():
            continue
        text = read_text(path)
        n = count_name_hits(text, deny["names"])
        h = count_handle_hits(text, deny["handles"])
        l = count_link_hits(text, deny["links"])
        at = len(YT_AT.findall(text))
        ch = len(YT_CHANNEL.findall(text))
        if n or h or l or at or ch:
            hits.append(f"data/{name}: names={n} handles={h} links={l} @={at} channel={ch}")
    assert not hits, (
        "Denylist values or youtube.com/@|/channel/ links appeared in public "
        f"data files that the app serves at /data/ ({hits}). Counts only; names "
        "are not printed."
    )
