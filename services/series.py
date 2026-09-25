"""Load curated TV series catalog (trailer-ready only)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from data.series_shows import SERIES_SHOWS, all_series, total_series, years_span_label
from services.tmdb import PLACEHOLDER_POSTER, backdrop_url, poster_url

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "series_catalog.json"
_YT = re.compile(r"^[A-Za-z0-9_-]{11}$")


def legal_watch_tv_url(tv_id: int) -> str:
    return f"https://www.themoviedb.org/tv/{tv_id}/watch"


def _valid_trailer(key: str | None) -> bool:
    if not key or not _YT.fullmatch(key):
        return False
    if key.startswith("mobile") or key.endswith("-") or "web-" in key:
        return False
    return True


def _load_resolved() -> list[dict[str, Any]]:
    if not CATALOG_PATH.exists():
        return []
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        return [
            row
            for row in data
            if row.get("id") and _valid_trailer(row.get("trailer_key"))
        ]
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
    }


def series_stats() -> dict[str, Any]:
    resolved = _load_resolved()
    return {
        "planned": total_series(),
        "resolved": len(resolved),
        "with_trailer": len(resolved),
    }


def all_series_entries() -> list[dict[str, Any]]:
    resolved = {r.get("query"): r for r in _load_resolved()}
    out: list[dict[str, Any]] = []
    for planned in all_series():
        title = planned["title"]
        if title in resolved:
            out.append(_normalize_entry(resolved[title], planned))
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


def series_year_index() -> list[dict[str, Any]]:
    entries = all_series_entries()
    counts: dict[int, int] = {}
    for show in entries:
        y = show.get("start")
        if not y:
            continue
        y = int(y)
        counts[y] = counts.get(y, 0) + 1
    return [
        {
            "year": y,
            "planned": counts[y],
            "resolved": counts[y],
            "with_trailer": counts[y],
        }
        for y in sorted(counts.keys(), reverse=True)
    ]


def series_shelf(selected_year: int | None = None) -> dict[str, Any]:
    years = series_year_index()
    if not years:
        return {"years": [], "selected_year": None, "shows": []}
    valid = {y["year"] for y in years}
    if selected_year not in valid:
        selected_year = years[0]["year"]
    shows = [
        s for s in all_series_entries() if s.get("start") and int(s["start"]) == selected_year
    ]
    return {"years": years, "selected_year": selected_year, "shows": shows}


def search_catalog(query: str, limit: int = 48) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []
    hits = []
    for show in all_series_entries():
        title = (show.get("title") or "").lower()
        query_title = (show.get("query") or "").lower()
        if q in title or q in query_title:
            hits.append(show)
    hits.sort(key=lambda s: (s.get("start") or 0), reverse=True)
    return hits[:limit]


def series_by_queries(titles: list[str]) -> list[dict[str, Any]]:
    by_query = {r.get("query"): r for r in _load_resolved()}
    by_title = {(r.get("title") or "").lower(): r for r in _load_resolved()}
    out = []
    for title in titles:
        row = by_query.get(title) or by_title.get(title.lower())
        if row:
            planned = next((p for p in SERIES_SHOWS if p["title"] == title), None)
            out.append(_normalize_entry(row, planned))
    return out
