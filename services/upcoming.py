"""Upcoming Oct–Dec 2026 movies and Fall 2026 series shelves."""

from __future__ import annotations

from typing import Any

from data.upcoming import UPCOMING_MOVIES_2026, UPCOMING_SERIES
from services import library, series


def upcoming_movies() -> list[dict[str, Any]]:
    """Return upcoming movies that have on-site trailers; others as coming-soon cards."""
    matched = {m.get("query") or m.get("title"): m for m in library.movies_by_queries(UPCOMING_MOVIES_2026)}
    by_title = {(m.get("title") or "").lower(): m for m in library.all_trailer_movies()}
    out: list[dict[str, Any]] = []
    for title in UPCOMING_MOVIES_2026:
        hit = matched.get(title) or by_title.get(title.lower())
        if hit and hit.get("trailer_key"):
            card = dict(hit)
            card["status"] = "trailer"
            out.append(card)
        else:
            out.append(
                {
                    "title": title,
                    "year": 2026,
                    "status": "coming",
                    "media_type": "movie",
                    "overview": "Coming October–December 2026. Trailer will appear here when available.",
                }
            )
    return out


def upcoming_series() -> list[dict[str, Any]]:
    matched = {s.get("query") or s.get("title"): s for s in series.series_by_queries(UPCOMING_SERIES)}
    by_title = {(s.get("title") or "").lower(): s for s in series.all_series_entries()}
    out: list[dict[str, Any]] = []
    for title in UPCOMING_SERIES:
        hit = matched.get(title) or by_title.get(title.lower())
        if hit and hit.get("trailer_key"):
            card = dict(hit)
            card["status"] = "trailer"
            out.append(card)
        else:
            out.append(
                {
                    "title": title,
                    "years": "Fall 2026",
                    "status": "coming",
                    "media_type": "tv",
                    "overview": "Coming Fall 2026. Trailer will appear here when available.",
                }
            )
    return out


def upcoming_payload() -> dict[str, Any]:
    movies = upcoming_movies()
    shows = upcoming_series()
    return {
        "movies": movies,
        "series": shows,
        "movie_count": len(movies),
        "series_count": len(shows),
        "with_trailer": sum(1 for m in movies if m.get("status") == "trailer")
        + sum(1 for s in shows if s.get("status") == "trailer"),
    }
