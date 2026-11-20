"""Helpers for the Sentinel QA suite. Never include denylist values in assertion messages."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DENYLIST = Path("/workspace/shared/2daymovie-channels.json")
YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
ALLOWED_TYPES = frozenset({"movies", "series", "kids", "cartoons", "ai", "wildlife"})
TEXT_SUFFIXES = {
    ".html", ".htm", ".js", ".css", ".svg", ".txt", ".json", ".xml",
    ".md", ".jinja", ".j2", ".map",
}

# Routes that are parameterized or that we exercise with explicit fixtures.
SKIP_ENDPOINTS = frozenset({"static"})


def public_get_rules(app) -> list:
    """Return GET/HEAD url_map rules that should be probed for HTTP 200."""
    rules = []
    for rule in app.url_map.iter_rules():
        if "GET" not in rule.methods:
            continue
        if rule.endpoint in SKIP_ENDPOINTS:
            continue
        rules.append(rule)
    return rules


def html_routes(app) -> list[str]:
    """Concrete paths that render HTML (skip metrics, health, JSON, static)."""
    skip_ends = SKIP_ENDPOINTS | {"metrics", "healthz", "readyz", "data", "robots"}
    paths = []
    for rule in app.url_map.iter_rules():
        if "GET" not in rule.methods:
            continue
        if rule.endpoint in skip_ends:
            continue
        if "<" in rule.rule:
            continue
        paths.append(rule.rule)
    return paths


def iter_text_files(base: Path) -> Iterable[Path]:
    if not base.exists():
        return
    if base.is_file():
        yield base
        return
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", ".venv", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.suffix == "":
            yield path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def denylist_path() -> Path | None:
    raw = os.environ.get("CHANNELS_DENYLIST", "").strip()
    path = Path(raw) if raw else DEFAULT_DENYLIST
    return path if path.is_file() else None


def load_denylist() -> dict | None:
    """Return {names, handles, links} or None if the denylist file is missing.

    Names and handles are collected for matching; callers must never print them.
    """
    path = denylist_path()
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        data = data.get("channels") or data.get("items") or []
    names: set[str] = set()
    handles: set[str] = set()
    links: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if name:
            names.add(name)
            short = name.split(" — ")[0].strip()
            if short:
                names.add(short)
        url = (item.get("url") or "").strip()
        if url:
            links.add(url)
            parsed = urlparse(url)
            host = (parsed.netloc or "").lower()
            if "youtube.com" in host or host.endswith("youtu.be"):
                path = parsed.path or ""
                m = re.search(r"/@([^/?#\s]+)", path)
                if m:
                    handles.add(m.group(1))
                m = re.search(r"/channel/(UC[A-Za-z0-9_-]{22})", path)
                if m:
                    handles.add(m.group(1))
                # Bare /username paths (no @ or /channel/)
                parts = [p for p in path.split("/") if p]
                if len(parts) == 1 and not parts[0].startswith("@"):
                    handles.add(parts[0])
    return {"names": names, "handles": handles, "links": links, "count": len(data)}


DENYLIST_MISSING_MSG = (
    "Channel denylist not found. Set CHANNELS_DENYLIST to a JSON file path "
    "or place the shared denylist at /workspace/shared/2daymovie-channels.json. "
    "The file is intentionally not committed (committing names/handles would itself be a leak)."
)


def count_name_hits(text: str, names: set[str]) -> int:
    return sum(1 for name in names if name and name in text)


def count_handle_hits(text: str, handles: set[str]) -> int:
    """Match @handle, youtube.com/@handle, /channel/UC..., or /username tokens."""
    hits = 0
    for handle in handles:
        if not handle:
            continue
        if handle.startswith("UC") and len(handle) >= 20:
            if f"/channel/{handle}" in text or handle in text:
                hits += 1
                continue
        if re.search(rf"youtube\.com/@{re.escape(handle)}(?:[/?#\"'\s]|$)", text, re.I):
            hits += 1
            continue
        if re.search(rf"@{re.escape(handle)}(?:[/?#\"'\s]|$)", text):
            hits += 1
    return hits


def count_link_hits(text: str, links: set[str]) -> int:
    return sum(1 for link in links if link and link in text)
