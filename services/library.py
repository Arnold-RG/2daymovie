"""Load curated 2000–2026 year catalog (resolved TMDB metadata)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data.year_movies import YEAR_MOVIES, all_years, titles_for_year, total_titles
from services.tmdb import (
    PLACEHOLDER_POSTER,
    backdrop_url,
    get_movie,
    legal_watch_url,
    poster_url,
    search_movies,
    using_live_api,
)

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "year_catalog.json"


def _load_resolved() -> list[dict[str, Any]]:
    if not CATALOG_PATH.exists():
        return []
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        return [row for row in data if row.get("id")]
    except Exception:
        return []


def _normalize_entry(row: dict[str, Any]) -> dict[str, Any]:
    mid = row["id"]
    return {
        "id": mid,
        "title": row.get("title") or row.get("query") or "Untitled",
        "overview": row.get("overview") or "",
        "year": row.get("year"),
        "release_date": row.get("release_date") or f"{row.get('year', '')}-01-01",
        "vote_average": row.get("vote_average") or 0,
        "poster": poster_url(row.get("poster_path")) or PLACEHOLDER_POSTER,
        "backdrop": backdrop_url(row.get("backdrop_path"))
        or poster_url(row.get("poster_path"))
        or PLACEHOLDER_POSTER,
        "trailer_key": row.get("trailer_key"),
        "watch_link": row.get("watch_link") or legal_watch_url(mid),
        "query": row.get("query"),
    }


def library_stats() -> dict[str, Any]:
    resolved = _load_resolved()
    with_trailer = sum(1 for r in resolved if r.get("trailer_key"))
    return {
        "planned": total_titles(),
        "resolved": len(resolved),
        "with_trailer": with_trailer,
        "years": all_years(),
    }


def movies_for_year(year: int) -> list[dict[str, Any]]:
    resolved = {f"{r.get('year')}|{r.get('query')}": r for r in _load_resolved()}
    titles = titles_for_year(year)
    out: list[dict[str, Any]] = []

    for title in titles:
        key = f"{year}|{title}"
        if key in resolved:
            out.append(_normalize_entry(resolved[key]))
            continue

        # Live TMDB search fallback
        if using_live_api():
            hits = search_movies(title, page=1).get("results") or []
            pick = None
            for h in hits:
                if str(h.get("year")) == str(year):
                    pick = h
                    break
            pick = pick or (hits[0] if hits else None)
            if pick:
                detail = get_movie(pick["id"]) or pick
                detail["year"] = year
                detail["query"] = title
                detail["watch_link"] = legal_watch_url(pick["id"])
                out.append(detail)
                continue

        # Placeholder card until resolved
        out.append(
            {
                "id": None,
                "title": title,
                "overview": "Catalog entry pending metadata sync.",
                "year": year,
                "poster": PLACEHOLDER_POSTER,
                "backdrop": None,
                "trailer_key": None,
                "watch_link": None,
                "pending": True,
            }
        )
    return out


def year_index() -> list[dict[str, Any]]:
    resolved = _load_resolved()
    counts: dict[int, int] = {y: 0 for y in YEAR_MOVIES}
    trailers: dict[int, int] = {y: 0 for y in YEAR_MOVIES}
    for row in resolved:
        y = row.get("year")
        if y in counts:
            counts[y] += 1
            if row.get("trailer_key"):
                trailers[y] += 1
    return [
        {
            "year": y,
            "planned": len(YEAR_MOVIES[y]),
            "resolved": counts.get(y, 0),
            "with_trailer": trailers.get(y, 0),
        }
        for y in all_years()
    ]
