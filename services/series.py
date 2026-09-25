"""Load curated TV series catalog (resolved TMDB metadata)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data.series_shows import SERIES_SHOWS, all_series, total_series, years_span_label
from services.tmdb import (
    PLACEHOLDER_POSTER,
    backdrop_url,
    poster_url,
)

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "series_catalog.json"


def legal_watch_tv_url(tv_id: int) -> str:
    return f"https://www.themoviedb.org/tv/{tv_id}/watch"


def _load_resolved() -> list[dict[str, Any]]:
    if not CATALOG_PATH.exists():
        return []
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        return [row for row in data if row.get("id")]
    except Exception:
        return []


def _normalize_entry(row: dict[str, Any], planned: dict[str, Any] | None = None) -> dict[str, Any]:
    mid = row["id"]
    start = row.get("start") or (planned or {}).get("start")
    end = row.get("end") if row.get("end") is not None else (planned or {}).get("end")
    span = {
        "title": row.get("title") or row.get("query") or "Untitled",
        "start": start,
        "end": end,
    }
    return {
        "id": mid,
        "title": span["title"],
        "overview": row.get("overview") or "",
        "start": start,
        "end": end,
        "years": years_span_label(span),
        "year": start,
        "vote_average": row.get("vote_average") or 0,
        "poster": poster_url(row.get("poster_path")) or PLACEHOLDER_POSTER,
        "backdrop": backdrop_url(row.get("backdrop_path"))
        or poster_url(row.get("poster_path"))
        or PLACEHOLDER_POSTER,
        "trailer_key": row.get("trailer_key"),
        "watch_link": row.get("watch_link") or legal_watch_tv_url(mid),
        "query": row.get("query"),
        "media_type": "tv",
        "seasons": row.get("seasons"),
        "status": row.get("status"),
    }


def series_stats() -> dict[str, Any]:
    resolved = _load_resolved()
    with_trailer = sum(1 for r in resolved if r.get("trailer_key"))
    return {
        "planned": total_series(),
        "resolved": len(resolved),
        "with_trailer": with_trailer,
    }


def all_series_entries() -> list[dict[str, Any]]:
    resolved = {r.get("query"): r for r in _load_resolved()}
    out: list[dict[str, Any]] = []
    for planned in all_series():
        title = planned["title"]
        if title in resolved:
            out.append(_normalize_entry(resolved[title], planned))
            continue
        out.append(
            {
                "id": None,
                "title": title,
                "overview": "Series entry pending metadata sync.",
                "start": planned["start"],
                "end": planned["end"],
                "years": years_span_label(planned),
                "year": planned["start"],
                "poster": PLACEHOLDER_POSTER,
                "backdrop": None,
                "trailer_key": None,
                "watch_link": None,
                "pending": True,
                "media_type": "tv",
            }
        )
    # Newest first for browsing
    out.sort(key=lambda s: (s.get("start") or 0, s.get("title") or ""), reverse=True)
    return out


def get_series(tv_id: int) -> dict[str, Any] | None:
    for row in _load_resolved():
        if row.get("id") == tv_id:
            planned = next(
                (p for p in SERIES_SHOWS if p["title"] == row.get("query")), None
            )
            return _normalize_entry(row, planned)
    return None


def series_by_decade() -> list[dict[str, Any]]:
    entries = all_series_entries()
    decades = [
        ("2020s", 2020, 2029),
        ("2010s", 2010, 2019),
        ("2000s", 2000, 2009),
        ("1990s", 1990, 1999),
    ]
    blocks = []
    for label, start, end in decades:
        shows = [s for s in entries if s.get("start") and start <= int(s["start"]) <= end]
        if shows:
            blocks.append({"label": label, "shows": shows})
    return blocks
