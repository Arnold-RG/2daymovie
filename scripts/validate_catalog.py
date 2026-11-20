#!/usr/bin/env python3
"""Validate data/catalog.json: schema, uniqueness, and no leaked channel names/URLs.

    python scripts/validate_catalog.py
    python scripts/validate_catalog.py --catalog data/catalog.json --channels scripts/channels.json

Show-name channels (Peppa Pig, Mr Bean, Bluey, ...) may appear in a title because
they are the title of the work. They are reported as allowed exceptions. Brand-like
channel names, every channel URL, @handle and channel id are hard failures.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
TYPES = {"movies", "series", "kids", "cartoons", "ai", "wildlife"}
ITEM_KEYS = {"id", "title", "type", "genres", "duration", "thumbnail"}
ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
BRANDY = re.compile(
    r"\b(tv|movies?|films?|studios?|entertainment|channel|recaps?|cinema|official|flix|plus)\b",
    re.I,
)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def is_iso(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def channel_needles(ch: dict) -> dict:
    """Strings that must not appear in the public catalog (except show names in titles)."""
    names = [ch["name"]]
    url = (ch.get("url") or "").strip()
    handles, ids, urls = [], [], []
    if url:
        urls.append(url)
        urls.append(url.rstrip("/"))
        path = urlparse(url).path.rstrip("/")
        last = path.split("/")[-1] if path else ""
        if last.startswith("@"):
            handles.append(last)
            handles.append(last[1:])
        elif last.startswith("UC") and len(last) >= 20:
            ids.append(last)
    return {"name": ch["name"], "names": names, "urls": [u for u in urls if u], "handles": handles, "ids": ids, "brand": bool(BRANDY.search(ch["name"]))}


def find_in_text(needle: str, text: str, title_text: str) -> str | None:
    if not needle:
        return None
    # URLs and handles: case-sensitive-enough exact substring
    if needle.startswith("http") or needle.startswith("@"):
        return "body" if needle.lower() in text.lower() else None
    # Multi-word or long names: case-insensitive phrase
    if len(needle) < 4:
        return None
    pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(needle) + r"(?![A-Za-z0-9])", re.I)
    if pat.search(text):
        if (not pat.search(text[: text.find("\n\"title\"") + 1] if False else title_text)) and pat.search(text):
            # decide later
            pass
        in_title = bool(pat.search(title_text))
        in_elsewhere = bool(pat.search(text)) and (
            pat.search(re.sub(r'"title"\s*:\s*".*?"', "", text)) if True else True
        )
        # We'll compute elsewhere more carefully in main
        return "maybe"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default=str(ROOT / "data" / "catalog.json"))
    ap.add_argument("--channels", default=str(ROOT / "scripts" / "channels.json"))
    args = ap.parse_args()

    cat_path = Path(args.catalog)
    ch_path = Path(args.channels)
    errors: list[str] = []
    warnings: list[str] = []

    try:
        catalog = json.loads(cat_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: cannot read catalog: {e}", file=sys.stderr)
        return 2

    if not isinstance(catalog, dict):
        errors.append("catalog must be an object with 'generated' and 'items'")
        catalog = {}
    if not is_iso(catalog.get("generated")):
        errors.append(f"generated must be an ISO-8601 timestamp, got {catalog.get('generated')!r}")
    items = catalog.get("items")
    if not isinstance(items, list):
        errors.append("items must be an array")
        items = []

    ids: set[str] = set()
    titles: list[str] = []
    for i, it in enumerate(items):
        loc = f"items[{i}]"
        if not isinstance(it, dict):
            errors.append(f"{loc} is not an object")
            continue
        extra = set(it) - ITEM_KEYS
        if extra:
            errors.append(f"{loc} has unexpected fields: {sorted(extra)}")
        missing = ITEM_KEYS - set(it)
        if missing:
            errors.append(f"{loc} missing fields: {sorted(missing)}")
            continue
        if not isinstance(it["id"], str) or not ID_RE.match(it["id"]):
            errors.append(f"{loc}.id is not a YouTube video id: {it['id']!r}")
        elif it["id"] in ids:
            errors.append(f"{loc}.id is a duplicate: {it['id']}")
        else:
            ids.add(it["id"])
        if not isinstance(it["title"], str) or not it["title"].strip():
            errors.append(f"{loc}.title is empty")
        else:
            titles.append(it["title"])
        if it.get("type") not in TYPES:
            errors.append(f"{loc}.type must be one of {sorted(TYPES)}, got {it.get('type')!r}")
        genres = it.get("genres")
        if not isinstance(genres, list) or not genres or not all(isinstance(g, str) and g.strip() for g in genres):
            errors.append(f"{loc}.genres must be a non-empty array of strings (genres[0] is the row name)")
        if not isinstance(it.get("duration"), int) or isinstance(it.get("duration"), bool) or it["duration"] <= 0:
            errors.append(f"{loc}.duration must be a positive int (seconds)")
        thumb = it.get("thumbnail")
        if not isinstance(thumb, str) or not thumb.startswith("https://"):
            errors.append(f"{loc}.thumbnail must be an https URL")

    channels = json.loads(ch_path.read_text(encoding="utf-8"))
    # Texts: full catalog, titles only, non-title fields
    raw = json.dumps(catalog, ensure_ascii=False)
    title_blob = "\n".join(titles)
    stripped = json.loads(json.dumps(catalog, ensure_ascii=False))
    for it in stripped.get("items") or []:
        if isinstance(it, dict):
            it["title"] = ""
    elsewhere = json.dumps(stripped, ensure_ascii=False)

    allowed_title_hits: list[str] = []
    for ch in channels:
        info = channel_needles(ch)
        name = info["name"]
        for u in info["urls"]:
            if u and u.lower() in raw.lower():
                errors.append(f"channel URL leaked: {u}")
        for h in info["handles"]:
            # Only the @handle form is a leak; bare show names in titles are handled below.
            at = h if h.startswith("@") else "@" + h
            if re.search(r"(?i)(?<![A-Za-z0-9])" + re.escape(at) + r"(?![A-Za-z0-9])", raw):
                errors.append(f"channel handle leaked: {at} ({name})")
        for cid in info["ids"]:
            if cid in raw:
                errors.append(f"channel id leaked: {cid} ({name})")
        pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])", re.I)
        if not pat.search(raw):
            continue
        in_else = bool(pat.search(elsewhere))
        in_title = bool(pat.search(title_blob))
        if in_else:
            errors.append(f"channel name leaked outside titles: {name}")
        elif in_title:
            if info["brand"]:
                errors.append(f"brand-like channel name in a title: {name}")
            else:
                allowed_title_hits.append(name)

    print(f"catalog: {len(items)} items, generated {catalog.get('generated')}")
    if allowed_title_hits:
        print(f"allowed show-name title mentions ({len(allowed_title_hits)}): " + ", ".join(allowed_title_hits))
    if warnings:
        for w in warnings:
            print(f"warning: {w}")
    if errors:
        print(f"{len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
