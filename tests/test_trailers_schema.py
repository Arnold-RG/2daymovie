"""data/trailers.json public schema."""
from __future__ import annotations

import json
from datetime import date, datetime

from tests.helpers import ROOT, YT_ID


def _load():
    path = ROOT / "data" / "trailers.json"
    assert path.is_file(), "data/trailers.json is missing (Forge has not added trailers yet)"
    return json.loads(path.read_text(encoding="utf-8"))


def test_trailers_top_level_shape():
    doc = _load()
    assert isinstance(doc, dict), "trailers must be an object"
    assert isinstance(doc["items"], list) and doc["items"], "trailers.items must be a non-empty list"


def test_trailers_item_schema():
    items = _load()["items"]
    required = {"title", "release_date", "youtube_id", "start", "end"}
    problems = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            problems.append(f"item[{i}] is not an object")
            continue
        missing = required - set(item)
        if missing:
            problems.append(f"item[{i}] missing keys {sorted(missing)}")
            continue
        if not isinstance(item["title"], str) or not item["title"].strip():
            problems.append(f"item[{i}] title is empty")
        if not isinstance(item["youtube_id"], str) or not YT_ID.match(item["youtube_id"]):
            problems.append(f"item[{i}] youtube_id is not an 11-char YouTube id")
        raw_date = item["release_date"]
        try:
            if isinstance(raw_date, datetime):
                date.fromisoformat(raw_date.date().isoformat())
            else:
                date.fromisoformat(str(raw_date))
        except ValueError:
            problems.append(f"item[{i}] release_date is not an ISO date")
        start, end = item["start"], item["end"]
        if type(start) is not int or type(end) is not int:
            problems.append(f"item[{i}] start/end must be ints")
        elif not end > start:
            problems.append(f"item[{i}] end must be greater than start")
    assert not problems, f"{len(problems)} trailer schema problem(s): {problems[:20]}"
