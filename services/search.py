"""Local catalog search (movies + series) with trailer-required results."""

from __future__ import annotations

from typing import Any

from services import library, series


def _score(title: str, query: str) -> int:
    t = title.lower()
    q = query.lower()
    if t == q:
        return 300
    if t.startswith(q):
        return 200
    if q in t:
        return 100
    t_parts = set(t.replace(":", " ").replace("-", " ").split())
    q_parts = set(q.replace(":", " ").replace("-", " ").split())
    return 10 * len(t_parts & q_parts)


def search_catalog(query: str, page: int = 1, per_page: int = 24) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"results": [], "page": 1, "total_pages": 1, "total_results": 0}

    hits: list[dict[str, Any]] = []

    for movie in library.all_trailer_movies():
        score = max(
            _score(movie.get("title") or "", q),
            _score(movie.get("query") or "", q),
        )
        if score <= 0:
            continue
        item = dict(movie)
        item["media_type"] = "movie"
        item["_score"] = score
        hits.append(item)

    for show in series.all_series_entries():
        if not show.get("trailer_key"):
            continue
        score = max(
            _score(show.get("title") or "", q),
            _score(show.get("query") or "", q),
        )
        if score <= 0:
            continue
        item = dict(show)
        item["media_type"] = "tv"
        item["_score"] = score
        hits.append(item)

    best: dict[tuple[str, int], dict[str, Any]] = {}
    for item in hits:
        key = (item["media_type"], int(item["id"]))
        if key not in best or item["_score"] > best[key]["_score"]:
            best[key] = item

    ranked = sorted(
        best.values(),
        key=lambda m: (m["_score"], m.get("vote_average") or 0, m.get("year") or 0),
        reverse=True,
    )
    total = len(ranked)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    chunk = ranked[start : start + per_page]
    for item in chunk:
        item.pop("_score", None)

    return {
        "results": chunk,
        "page": page,
        "total_pages": total_pages,
        "total_results": total,
    }
