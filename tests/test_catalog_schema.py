"""Extra catalog contract checks not already in tests/test_app.py.

Item-level unique ids, allowed types, genres, duration, and thumbnail
shape are asserted by test_catalog_schema_and_ids in test_app.py. This
module only covers the top-level document shape from the QA spec.
"""
from __future__ import annotations

import json

from tests.helpers import ROOT


def _load():
    path = ROOT / "data" / "catalog.json"
    assert path.is_file(), "data/catalog.json is missing (Forge has not added the catalog yet)"
    return json.loads(path.read_text(encoding="utf-8"))


def test_catalog_top_level_shape():
    doc = _load()
    assert isinstance(doc, dict), "catalog must be an object, not a bare list"
    assert "generated" in doc and doc["generated"], "catalog.generated is required"
    assert isinstance(doc["items"], list) and doc["items"], "catalog.items must be a non-empty list"
