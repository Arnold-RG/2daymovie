"""Fail if source-channel names, handles, or /@ links appear in *our* surfaces.

Scope (first-party only):
  - server-rendered HTML from this Flask app
  - templates/
  - static/
  - the exported site under docs/
  - public data files (data/catalog.json, data/trailers.json, and the
    copies under docs/data/)

Out of scope: the YouTube player chrome inside a youtube-nocookie iframe
(uploader name, avatar, channel link). That UI is controlled by YouTube
and cannot be hidden by us. These tests never fetch iframe, oEmbed, or
youtube.com / youtube-nocookie.com content.

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

# Public JSON that the client renders as titles/rows. Kept separate from
# HTML/asset scans so a title hit does not look like a template leak.
PUBLIC_DATA_FILES = (
    ROOT / "data" / "catalog.json",
    ROOT / "data" / "trailers.json",
    ROOT / "docs" / "data" / "catalog.json",
    ROOT / "docs" / "data" / "trailers.json",
)


def _html_and_asset_sources(client, app) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    for path in html_routes(app):
        resp = client.get(path)
        sources.append((f"GET {path} (status {resp.status_code})", resp.get_data(as_text=True)))
    resp = client.get("/this-path-should-not-exist-qa-404")
    sources.append((f"GET 404 page (status {resp.status_code})", resp.get_data(as_text=True)))
    for folder in (ROOT / "static", ROOT / "templates", ROOT / "docs"):
        for file in iter_text_files(folder):
            # Public JSON is checked in the data-file test; skip it here so
            # a catalog title hit is reported against the data file, not docs/.
            if file.parent.name == "data" and file.suffix == ".json":
                continue
            sources.append((str(file.relative_to(ROOT)), read_text(file)))
    return sources


def _data_sources() -> list[tuple[str, str]]:
    sources = []
    for path in PUBLIC_DATA_FILES:
        if path.is_file():
            sources.append((str(path.relative_to(ROOT)), read_text(path)))
    return sources


def test_denylist_not_in_html_templates_static_or_exported_docs(client, app):
    """Our HTML and assets only. Does not inspect YouTube iframe content."""
    deny = load_denylist()
    if deny is None:
        pytest.skip(DENYLIST_MISSING_MSG + f" (looked at {denylist_path()})")
    hits = []
    for label, text in _html_and_asset_sources(client, app):
        n = count_name_hits(text, deny["names"])
        h = count_handle_hits(text, deny["handles"])
        l = count_link_hits(text, deny["links"])
        if n or h or l:
            hits.append(f"{label}: names={n} handles={h} links={l}")
    assert not hits, (
        "Source-channel denylist values appeared in rendered HTML, templates/, "
        f"static/, or exported docs/ (excluding public JSON) ({len(hits)} "
        f"surface(s): {hits})"
    )


def test_no_youtube_at_or_channel_links_in_our_html_and_assets(client, app):
    """Forbids youtube.com/@ and /channel/ in our HTML/assets, not in iframes."""
    hits = []
    for label, text in _html_and_asset_sources(client, app):
        at = len(YT_AT.findall(text))
        ch = len(YT_CHANNEL.findall(text))
        if at or ch:
            hits.append(f"{label}: youtube.com/@={at} youtube.com/channel/={ch}")
    assert not hits, (
        "youtube.com/@ or youtube.com/channel/ links appeared in rendered HTML, "
        f"templates/, static/, or exported docs/ ({hits})"
    )


def test_denylist_not_in_public_catalog_or_trailers():
    """Public JSON is fetched by the client and titles are shown in our UI."""
    deny = load_denylist()
    if deny is None:
        pytest.skip(DENYLIST_MISSING_MSG)
    hits = []
    for label, text in _data_sources():
        n = count_name_hits(text, deny["names"])
        h = count_handle_hits(text, deny["handles"])
        l = count_link_hits(text, deny["links"])
        at = len(YT_AT.findall(text))
        ch = len(YT_CHANNEL.findall(text))
        if n or h or l or at or ch:
            hits.append(f"{label}: names={n} handles={h} links={l} @={at} channel={ch}")
    assert not hits, (
        "Denylist values or youtube.com/@|/channel/ links appeared in public "
        f"data files ({hits}). Counts only; names are not printed."
    )
