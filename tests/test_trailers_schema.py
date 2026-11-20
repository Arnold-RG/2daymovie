"""Extra trailers contract checks not already in tests/test_app.py.

Item keys, youtube_id shape, start < end, and uniqueness versus the
catalog are asserted by test_trailers_upcoming_and_include_avengers_doomsday
in test_app.py. This module only adds ISO-date validation and the
top-level document shape from the QA spec.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from tests.helpers import ROOT


def _load():
    path = ROOT / "data" / "trailers.json"
    assert path.is_file(), "data/trailers.json is missing (Forge has not added trailers yet)"
    return json.loads(path.read_text(encoding="utf-8"))


def test_trailers_top_level_shape():
    doc = _load()
    assert isinstance(doc, dict), "trailers must be an object"
    assert isinstance(doc["items"], list) and doc["items"], "trailers.items must be a non-empty list"


def test_trailers_release_dates_are_iso():
    items = _load()["items"]
    problems = []
    for i, item in enumerate(items):
        raw = item.get("release_date")
        try:
            if isinstance(raw, datetime):
                date.fromisoformat(raw.date().isoformat())
            else:
                date.fromisoformat(str(raw))
        except (TypeError, ValueError):
            problems.append(f"item[{i}] release_date is not an ISO date")
    assert not problems, problems
