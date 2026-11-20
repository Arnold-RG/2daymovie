"""data/catalog.json public schema."""
from __future__ import annotations

import json

from tests.helpers import ALLOWED_TYPES, ROOT, YT_ID


def _load():
    path = ROOT / "data" / "catalog.json"
    assert path.is_file(), "data/catalog.json is missing (Forge has not added the catalog yet)"
    return json.loads(path.read_text(encoding="utf-8"))


def test_catalog_top_level_shape():
    doc = _load()
    assert isinstance(doc, dict), "catalog must be an object, not a bare list"
    assert "generated" in doc and doc["generated"], "catalog.generated is required"
    assert isinstance(doc["items"], list) and doc["items"], "catalog.items must be a non-empty list"


def test_catalog_item_schema_and_unique_ids():
    items = _load()["items"]
    required = {"id", "title", "type", "genres", "duration", "thumbnail"}
    problems = []
    ids = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            problems.append(f"item[{i}] is not an object")
            continue
        missing = required - set(item)
        if missing:
            problems.append(f"item[{i}] missing keys {sorted(missing)}")
            continue
        if not isinstance(item["id"], str) or not YT_ID.match(item["id"]):
            problems.append(f"item[{i}] id is not an 11-char YouTube id")
        ids.append(item["id"])
        if not isinstance(item["title"], str) or not item["title"].strip():
            problems.append(f"item[{i}] title is empty")
        if item["type"] not in ALLOWED_TYPES:
            problems.append(f"item[{i}] type {item['type']!r} not in allowed set")
        genres = item["genres"]
        if not isinstance(genres, list) or not genres or not all(isinstance(g, str) and g.strip() for g in genres):
            problems.append(f"item[{i}] genres must be a non-empty list of strings")
        duration = item["duration"]
        if type(duration) is not int or duration <= 0:
            problems.append(f"item[{i}] duration must be an int number of seconds > 0")
        if not isinstance(item["thumbnail"], str) or not item["thumbnail"].strip():
            problems.append(f"item[{i}] thumbnail is empty")
    unique = set(ids)
    if len(ids) != len(unique):
        problems.append(f"duplicate ids: {len(ids) - len(unique)}")
    assert not problems, f"{len(problems)} catalog schema problem(s), first 20: {problems[:20]}"
