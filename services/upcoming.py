"""Upcoming 2026–2027 movies and series shelves."""

from __future__ import annotations

import re
from typing import Any

from data.upcoming import (
    UPCOMING_MOVIES_2025,
    UPCOMING_MOVIES_2026,
    UPCOMING_MOVIES_2027,
    UPCOMING_SERIES,
)
from services import library, series


def _movie_cards(titles: list[str], year: int, blurb: str) -> list[dict[str, Any]]:
    matched = {m.get("query") or m.get("title"): m for m in library.movies_by_queries(titles)}
    by_title = {(m.get("title") or "").lower(): m for m in library.all_trailer_movies()}
    out: list[dict[str, Any]] = []
    for title in titles:
        hit = matched.get(title) or by_title.get(title.lower())
        if hit and hit.get("trailer_key"):
            card = dict(hit)
            card["status"] = "trailer"
            out.append(card)
        else:
            out.append(
                {
                    "title": title,
                    "year": year,
                    "status": "coming",
                    "media_type": "movie",
                    "overview": blurb,
                }
            )
    return out



def upcoming_movies_2025() -> list[dict[str, Any]]:
    return _movie_cards(
        UPCOMING_MOVIES_2025,
        2025,
        "Coming 2025. Trailer will appear here when available.",
    )

def upcoming_movies_2026() -> list[dict[str, Any]]:
    return _movie_cards(
        UPCOMING_MOVIES_2026,
        2026,
        "Coming 2026. Trailer will appear here when available.",
    )


def upcoming_movies_2027() -> list[dict[str, Any]]:
    return _movie_cards(
        UPCOMING_MOVIES_2027,
        2027,
        "Coming 2027. Trailer will appear here when available.",
    )


def upcoming_series() -> list[dict[str, Any]]:
    matched = {s.get("query") or s.get("title"): s for s in series.series_by_queries(UPCOMING_SERIES)}
    by_title = {(s.get("title") or "").lower(): s for s in series.all_series_entries()}
    by_query = {(s.get("query") or "").lower(): s for s in series.all_series_entries()}

    def _soft(title: str) -> str:
        t = (title or "").lower().strip()
        t = re.sub(r"\s+season\s+\d+$", "", t)
        t = re.sub(r"\s*:\s*elbaph arc$", "", t)
        return t

    soft_index = {_soft(k): v for k, v in {**by_title, **by_query}.items() if k}

    out: list[dict[str, Any]] = []
    for title in UPCOMING_SERIES:
        hit = (
            matched.get(title)
            or by_title.get(title.lower())
            or by_query.get(title.lower())
            or soft_index.get(_soft(title))
        )
        if hit and hit.get("trailer_key"):
            card = dict(hit)
            card["status"] = "trailer"
            # Prefer the curated upcoming label in the shelf.
            card["title"] = title
            out.append(card)
        else:
            out.append(
                {
                    "title": title,
                    "years": "2026+",
                    "status": "coming",
                    "media_type": "tv",
                    "overview": "Coming soon. Trailer will appear here when available.",
                }
            )
    return out


def upcoming_payload() -> dict[str, Any]:
    movies_2025 = upcoming_movies_2025()
    movies_2026 = upcoming_movies_2026()
    movies_2027 = upcoming_movies_2027()
    shows = upcoming_series()
    all_movies = movies_2025 + movies_2026 + movies_2027
    return {
        "movies_2025": movies_2025,
        "movies": movies_2026,
        "movies_2027": movies_2027,
        "series": shows,
        "movie_count": len(all_movies),
        "series_count": len(shows),
        "with_trailer": sum(1 for m in all_movies if m.get("status") == "trailer")
        + sum(1 for s in shows if s.get("status") == "trailer"),
    }
