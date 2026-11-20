"""Internal source files must not be served or shipped in the exported site."""
from __future__ import annotations

from pathlib import Path

from tests.helpers import ROOT

# Paths that must not return the internal sources file (or any 2xx).
CATALOG_SOURCES_PATHS = (
    "/data/catalog_sources.json",
    "/data/./catalog_sources.json",
    "/static/../data/catalog_sources.json",
    "/static/js/../../data/catalog_sources.json",
    "/docs/data/catalog_sources.json",
    "/docs/../data/catalog_sources.json",
)

FORBIDDEN_EXPORT_NAMES = (
    "catalog_sources.json",
)


def test_catalog_sources_is_not_served(client):
    """Flask must 404 catalog_sources.json, including traversal-style paths."""
    leaked = []
    for path in CATALOG_SOURCES_PATHS:
        resp = client.get(path)
        if resp.status_code == 200:
            leaked.append(f"{path} returned 200 ({resp.mimetype}, {len(resp.data)} bytes)")
        elif resp.status_code not in {403, 404}:
            # Redirects that land on the file would also be a leak; follow once.
            if resp.status_code in {301, 302, 303, 307, 308}:
                location = resp.headers.get("Location", "")
                followed = client.get(path, follow_redirects=True)
                if followed.status_code == 200 and "catalog_sources" in location:
                    leaked.append(f"{path} redirected to {location} with 200")
                    continue
            leaked.append(f"{path} returned {resp.status_code}, expected 404")
    assert not leaked, leaked


def test_exported_docs_omits_internal_source_lists():
    """docs/ is the published GitHub Pages tree; source lists must not be in it."""
    docs = ROOT / "docs"
    assert docs.is_dir(), "docs/ (exported site) is missing"
    hits = []
    for path in docs.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(docs).as_posix()
        name = path.name
        if name in FORBIDDEN_EXPORT_NAMES:
            hits.append(rel)
        # scripts/channels.json, scripts/channels-compact.json, etc.
        if name.startswith("channels") and name.endswith(".json"):
            hits.append(rel)
        if rel.startswith("scripts/") and "channel" in name.lower():
            hits.append(rel)
    assert not hits, (
        "exported docs/ contains internal source-list file(s): "
        f"{sorted(set(hits))}"
    )


def test_exported_docs_has_no_scripts_directory():
    """The Pages export should not include the build scripts/ tree."""
    scripts = ROOT / "docs" / "scripts"
    assert not scripts.exists(), "docs/scripts/ should not exist in the exported site"
