"""Load curated film catalog (trailer-ready titles only)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from data.year_movies import YEAR_MOVIES, all_years, titles_for_year, total_titles
from services.tmdb import (
    PLACEHOLDER_POSTER,
    backdrop_url,
    poster_url,
)

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "year_catalog.json"
_YT = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _valid_trailer(key: str | None) -> bool:
    if not key or not _YT.fullmatch(key):
        return False
    if key.startswith("mobile") or key.endswith("-") or "web-" in key:
        return False
    return True


def _trailer_keys(row: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for key in list(row.get("trailer_keys") or []) + [row.get("trailer_key")]:
        if not _valid_trailer(key) or key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def _load_resolved() -> list[dict[str, Any]]:
    if not CATALOG_PATH.exists():
        return []
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        return [row for row in data if row.get("id") and _trailer_keys(row)]
    except Exception:
        return []


def _normalize_entry(row: dict[str, Any]) -> dict[str, Any]:
    mid = row["id"]
    keys = _trailer_keys(row)
    return {
        "id": mid,
        "title": row.get("title") or row.get("query") or "Untitled",
        "overview": row.get("overview") or "",
        "year": row.get("year"),
        "release_date": row.get("release_date") or f"{row.get('year', '')}-01-01",
        "vote_average": float(row.get("vote_average") or 0),
        "poster": poster_url(row.get("poster_path")) or PLACEHOLDER_POSTER,
        "backdrop": backdrop_url(row.get("backdrop_path"))
        or poster_url(row.get("poster_path"))
        or PLACEHOLDER_POSTER,
        "trailer_key": keys[0] if keys else None,
        "trailer_keys": keys,
        "watch_link": None,
        "query": row.get("query"),
        "genre_ids": list(row.get("genre_ids") or []),
        "media_type": "movie",
    }


def library_stats() -> dict[str, Any]:
    resolved = _load_resolved()
    return {
        "planned": total_titles(),
        "resolved": len(resolved),
        "with_trailer": len(resolved),
        "years": all_years(),
    }


def movies_for_year(year: int) -> list[dict[str, Any]]:
    """Return only titles that have an on-site trailer embed."""
    resolved = {f"{r.get('year')}|{r.get('query')}": r for r in _load_resolved()}
    out: list[dict[str, Any]] = []
    for title in titles_for_year(year):
        key = f"{year}|{title}"
        row = resolved.get(key)
        if not row:
            # fallback: match by title only within year
            row = next(
                (
                    r
                    for r in _load_resolved()
                    if r.get("year") == year
                    and (r.get("query") == title or r.get("title") == title)
                ),
                None,
            )
        if row:
            out.append(_normalize_entry(row))
    return out


def year_index() -> list[dict[str, Any]]:
    by_year: dict[int, list[dict[str, Any]]] = {y: [] for y in YEAR_MOVIES}
    for row in _load_resolved():
        y = row.get("year")
        if y in by_year:
            by_year[y].append(row)
    return [
        {
            "year": y,
            "planned": len(by_year[y]),
            "resolved": len(by_year[y]),
            "with_trailer": len(by_year[y]),
        }
        for y in all_years()
        if by_year.get(y)
    ]


def movies_shelf(selected_year: int | None = None) -> dict[str, Any]:
    years = year_index()
    if not years:
        return {"years": [], "selected_year": None, "movies": []}
    valid = {y["year"] for y in years}
    if selected_year not in valid:
        selected_year = years[0]["year"]
    return {
        "years": years,
        "selected_year": selected_year,
        "movies": movies_for_year(selected_year),
    }


def all_trailer_movies() -> list[dict[str, Any]]:
    return [_normalize_entry(r) for r in _load_resolved()]


def search_catalog(query: str, limit: int = 48) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []
    hits = []
    for movie in all_trailer_movies():
        title = (movie.get("title") or "").lower()
        query_title = (movie.get("query") or "").lower()
        if q in title or q in query_title:
            hits.append(movie)
    hits.sort(key=lambda m: (m.get("year") or 0), reverse=True)
    return hits[:limit]


def movies_by_queries(titles: list[str]) -> list[dict[str, Any]]:
    by_query = {r.get("query"): r for r in _load_resolved()}
    by_title = {(r.get("title") or "").lower(): r for r in _load_resolved()}
    out = []
    for title in titles:
        row = by_query.get(title) or by_title.get(title.lower())
        if row:
            out.append(_normalize_entry(row))
    return out


SORT_OPTIONS = (
    ("rating", "Top rated"),
    ("newest", "Newest"),
    ("oldest", "Oldest"),
    ("title", "Title A–Z"),
)


def _sort_movies(movies: list[dict[str, Any]], sort: str) -> list[dict[str, Any]]:
    items = list(movies)
    if sort == "newest":
        items.sort(key=lambda m: (m.get("year") or 0, m.get("vote_average") or 0), reverse=True)
    elif sort == "oldest":
        items.sort(key=lambda m: (m.get("year") or 9999, m.get("title") or ""))
    elif sort == "title":
        items.sort(key=lambda m: (m.get("title") or "").lower())
    else:  # rating
        items.sort(
            key=lambda m: (float(m.get("vote_average") or 0), m.get("year") or 0),
            reverse=True,
        )
    return items


def browse_catalog(
    page: int = 1,
    sort: str = "rating",
    per_page: int = 24,
) -> dict[str, Any]:
    allowed = {key for key, _ in SORT_OPTIONS}
    if sort not in allowed:
        sort = "rating"
    movies = _sort_movies(all_trailer_movies(), sort)
    total = len(movies)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    return {
        "results": movies[start : start + per_page],
        "page": page,
        "total_pages": total_pages,
        "total_results": total,
        "sort": sort,
    }


def movies_by_genre(
    genre_id: int,
    page: int = 1,
    sort: str = "rating",
    per_page: int = 24,
) -> dict[str, Any]:
    allowed = {key for key, _ in SORT_OPTIONS}
    if sort not in allowed:
        sort = "rating"
    matched = [
        m
        for m in all_trailer_movies()
        if genre_id in (m.get("genre_ids") or [])
    ]
    movies = _sort_movies(matched, sort)
    total = len(movies)
    total_pages = max(1, (total + per_page - 1) // per_page) if total else 1
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    return {
        "results": movies[start : start + per_page],
        "page": page,
        "total_pages": total_pages,
        "total_results": total,
        "sort": sort,
    }


def get_catalog_movie(movie_id: int) -> dict[str, Any] | None:
    for row in _load_resolved():
        if row.get("id") == movie_id:
            return _normalize_entry(row)
    return None
