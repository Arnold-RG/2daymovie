"""Movie data access: TMDB when configured, otherwise offline demo catalog."""

from __future__ import annotations

import os
from typing import Any

import requests

from data.demo_movies import DEMO_GENRES, DEMO_MOVIES

# media.themoviedb.org is the current public CDN; image.tmdb.org remains compatible.
IMAGE_BASE = "https://image.tmdb.org/t/p"
API_BASE = "https://api.themoviedb.org/3"
PLACEHOLDER_POSTER = "/static/img/poster-fallback.svg"
PLACEHOLDER_BACKDROP = "/static/img/backdrop-fallback.svg"


def _api_key() -> str | None:
    key = os.getenv("TMDB_API_KEY", "").strip()
    if not key or key.startswith("your_"):
        return None
    return key


def using_live_api() -> bool:
    return _api_key() is not None


def region() -> str:
    return os.getenv("TMDB_WATCH_REGION", "US").strip() or "US"


def poster_url(path: str | None, size: str = "w500") -> str | None:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{IMAGE_BASE}/{size}{path}"


def backdrop_url(path: str | None, size: str = "w1280") -> str | None:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{IMAGE_BASE}/{size}{path}"


def logo_url(path: str | None, size: str = "w92") -> str | None:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{IMAGE_BASE}/{size}{path}"


def poster_srcset(path: str | None) -> str | None:
    if not path or path.startswith("http"):
        return None
    sizes = ("w185", "w342", "w500", "w780")
    return ", ".join(f"{IMAGE_BASE}/{size}{path} {size[1:]}w" for size in sizes)


def backdrop_srcset(path: str | None) -> str | None:
    if not path or path.startswith("http"):
        return None
    sizes = ("w780", "w1280", "original")
    return ", ".join(
        f"{IMAGE_BASE}/{size}{path} {'2000' if size == 'original' else size[1:]}w"
        for size in sizes
    )


def year_of(date_str: str | None) -> str:
    if not date_str:
        return "—"
    return date_str[:4]


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    key = _api_key()
    if not key:
        raise RuntimeError("TMDB API key not configured")
    query = {"api_key": key, **(params or {})}
    response = requests.get(f"{API_BASE}{path}", params=query, timeout=12)
    response.raise_for_status()
    return response.json()


def _normalize_list_item(item: dict[str, Any]) -> dict[str, Any]:
    poster_path = item.get("poster_path")
    backdrop_path = item.get("backdrop_path") or poster_path
    poster = poster_url(poster_path) or PLACEHOLDER_POSTER
    backdrop = backdrop_url(backdrop_path) or poster
    return {
        "id": item["id"],
        "title": item.get("title") or item.get("name") or "Untitled",
        "overview": item.get("overview") or "",
        "release_date": item.get("release_date") or "",
        "year": year_of(item.get("release_date")),
        "vote_average": round(float(item.get("vote_average") or 0), 1),
        "genre_ids": item.get("genre_ids") or [],
        "poster": poster,
        "poster_srcset": poster_srcset(poster_path),
        "backdrop": backdrop,
        "backdrop_srcset": backdrop_srcset(backdrop_path if item.get("backdrop_path") else None),
        "fallback_poster": PLACEHOLDER_POSTER,
    }


def _demo_normalize(item: dict[str, Any]) -> dict[str, Any]:
    poster_path = item.get("poster_path")
    backdrop_path = item.get("backdrop_path") or poster_path
    poster = poster_url(poster_path) or PLACEHOLDER_POSTER
    backdrop = backdrop_url(backdrop_path) or poster
    return {
        "id": item["id"],
        "title": item["title"],
        "overview": item["overview"],
        "release_date": item["release_date"],
        "year": year_of(item["release_date"]),
        "vote_average": item["vote_average"],
        "genre_ids": item.get("genre_ids") or [],
        "poster": poster,
        "poster_srcset": poster_srcset(poster_path),
        "backdrop": backdrop,
        "backdrop_srcset": backdrop_srcset(item.get("backdrop_path")),
        "fallback_poster": PLACEHOLDER_POSTER,
        "runtime": item.get("runtime"),
        "genres": item.get("genres") or [],
        "trailer_key": item.get("trailer_key"),
        "providers": [
            {
                **p,
                "logo": logo_url(p.get("logo_path")),
            }
            for p in item.get("providers") or []
        ],
        "watch_link": item.get("watch_link"),
    }


def get_genres() -> list[dict[str, Any]]:
    if not using_live_api():
        genres = DEMO_GENRES
    else:
        data = _get("/genre/movie/list")
        genres = data.get("genres") or []
    return [
        g
        for g in genres
        if str(g.get("name") or "").strip().lower() not in {"adult", "nc-17"}
    ]


def get_trending(page: int = 1) -> dict[str, Any]:
    if not using_live_api():
        items = [_demo_normalize(m) for m in DEMO_MOVIES]
        return {"results": items, "page": 1, "total_pages": 1, "total_results": len(items)}
    data = _get("/trending/movie/week", {"page": page})
    return {
        "results": [_normalize_list_item(m) for m in data.get("results") or []],
        "page": data.get("page") or page,
        "total_pages": min(int(data.get("total_pages") or 1), 500),
        "total_results": data.get("total_results") or 0,
    }


def get_popular(page: int = 1) -> dict[str, Any]:
    if not using_live_api():
        ranked = sorted(DEMO_MOVIES, key=lambda m: m["vote_average"], reverse=True)
        items = [_demo_normalize(m) for m in ranked]
        return {"results": items, "page": 1, "total_pages": 1, "total_results": len(items)}
    data = _get("/movie/popular", {"page": page})
    return {
        "results": [_normalize_list_item(m) for m in data.get("results") or []],
        "page": data.get("page") or page,
        "total_pages": min(int(data.get("total_pages") or 1), 500),
        "total_results": data.get("total_results") or 0,
    }


def get_now_playing(page: int = 1) -> dict[str, Any]:
    if not using_live_api():
        recent = sorted(DEMO_MOVIES, key=lambda m: m["release_date"], reverse=True)
        items = [_demo_normalize(m) for m in recent]
        return {"results": items, "page": 1, "total_pages": 1, "total_results": len(items)}
    data = _get("/movie/now_playing", {"page": page})
    return {
        "results": [_normalize_list_item(m) for m in data.get("results") or []],
        "page": data.get("page") or page,
        "total_pages": min(int(data.get("total_pages") or 1), 500),
        "total_results": data.get("total_results") or 0,
    }


def get_top_rated(page: int = 1) -> dict[str, Any]:
    if not using_live_api():
        ranked = sorted(DEMO_MOVIES, key=lambda m: m["vote_average"], reverse=True)
        items = [_demo_normalize(m) for m in ranked]
        return {"results": items, "page": 1, "total_pages": 1, "total_results": len(items)}
    data = _get("/movie/top_rated", {"page": page})
    return {
        "results": [_normalize_list_item(m) for m in data.get("results") or []],
        "page": data.get("page") or page,
        "total_pages": min(int(data.get("total_pages") or 1), 500),
        "total_results": data.get("total_results") or 0,
    }


def discover_by_genre(genre_id: int, page: int = 1) -> dict[str, Any]:
    if not using_live_api():
        filtered = [m for m in DEMO_MOVIES if genre_id in (m.get("genre_ids") or [])]
        items = [_demo_normalize(m) for m in filtered]
        return {"results": items, "page": 1, "total_pages": 1, "total_results": len(items)}
    data = _get(
        "/discover/movie",
        {
            "with_genres": genre_id,
            "sort_by": "popularity.desc",
            "page": page,
            "include_adult": "false",
        },
    )
    return {
        "results": [_normalize_list_item(m) for m in data.get("results") or []],
        "page": data.get("page") or page,
        "total_pages": min(int(data.get("total_pages") or 1), 500),
        "total_results": data.get("total_results") or 0,
    }


def discover_movies(page: int = 1, sort_by: str = "popularity.desc") -> dict[str, Any]:
    if not using_live_api():
        return get_popular(page)
    data = _get(
        "/discover/movie",
        {
            "sort_by": sort_by,
            "page": page,
            "include_adult": "false",
            "vote_count.gte": 1,
        },
    )
    return {
        "results": [_normalize_list_item(m) for m in data.get("results") or []],
        "page": data.get("page") or page,
        "total_pages": min(int(data.get("total_pages") or 1), 500),
        "total_results": data.get("total_results") or 0,
    }


def search_movies(query: str, page: int = 1) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"results": [], "page": 1, "total_pages": 1, "total_results": 0}
    if not using_live_api():
        lowered = q.lower()
        hits = [_demo_normalize(m) for m in DEMO_MOVIES if lowered in m["title"].lower()]
        return {"results": hits, "page": 1, "total_pages": 1, "total_results": len(hits)}
    data = _get("/search/movie", {"query": q, "page": page, "include_adult": "false"})
    return {
        "results": [_normalize_list_item(m) for m in data.get("results") or []],
        "page": data.get("page") or page,
        "total_pages": min(int(data.get("total_pages") or 1), 500),
        "total_results": data.get("total_results") or 0,
    }


def _pick_trailer(videos: list[dict[str, Any]]) -> str | None:
    keys = _all_trailer_keys(videos)
    return keys[0] if keys else None


def _all_trailer_keys(videos: list[dict[str, Any]]) -> list[str]:
    """All official YouTube trailers (full trailers preferred, then teasers)."""
    preferred = []
    secondary = []
    for v in videos:
        if v.get("site") != "YouTube" or not v.get("key"):
            continue
        vtype = (v.get("type") or "").lower()
        if vtype == "trailer":
            preferred.append(v)
        elif vtype in {"teaser", "clip"}:
            secondary.append(v)

    def score(v: dict[str, Any]) -> tuple[int, int, int]:
        name = (v.get("name") or "").lower()
        return (
            1 if v.get("official") else 0,
            1 if "official" in name else 0,
            1 if "trailer" in name else 0,
        )

    preferred.sort(key=score, reverse=True)
    secondary.sort(key=score, reverse=True)
    keys: list[str] = []
    seen: set[str] = set()
    for v in preferred + secondary:
        key = v.get("key")
        if not key or key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys[:12]

def legal_watch_url(movie_id: int, title: str | None = None) -> str:
    """Legal where-to-watch page (TMDB). Never pirate indexes."""
    return f"https://www.themoviedb.org/movie/{movie_id}/watch"


def _providers_from_payload(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    country = payload.get(region()) or {}
    # TMDB often returns a JustWatch aggregator URL; we use TMDB watch page instead.
    link = None
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for bucket in ("flatrate", "rent", "buy", "free", "ads"):
        for item in country.get(bucket) or []:
            name = item.get("provider_name")
            if not name or name in seen:
                continue
            seen.add(name)
            collected.append(
                {
                    "provider_name": name,
                    "logo": logo_url(item.get("logo_path")),
                    "type": bucket,
                }
            )
    return collected, link


def get_movie(movie_id: int) -> dict[str, Any] | None:
    if not using_live_api():
        raw = next((m for m in DEMO_MOVIES if m["id"] == movie_id), None)
        if raw is None:
            return None
        movie = _demo_normalize(raw)
        movie["tagline"] = ""
        movie["cast"] = []
        movie["similar"] = [
            _demo_normalize(m) for m in DEMO_MOVIES if m["id"] != movie_id
        ][:6]
        movie["watch_link"] = legal_watch_url(movie_id, movie.get("title"))
        return movie

    try:
        detail = _get(
            f"/movie/{movie_id}",
            {"append_to_response": "videos,watch/providers,credits,similar"},
        )
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return None
        raise

    videos = (detail.get("videos") or {}).get("results") or []
    providers_root = (detail.get("watch/providers") or {}).get("results") or {}
    providers, _ignored_jw = _providers_from_payload(providers_root)

    poster_path = detail.get("poster_path")
    backdrop_path = detail.get("backdrop_path") or poster_path
    poster = poster_url(poster_path) or PLACEHOLDER_POSTER
    backdrop = backdrop_url(backdrop_path) or poster

    cast = []
    for person in ((detail.get("credits") or {}).get("cast") or [])[:12]:
        cast.append(
            {
                "name": person.get("name") or "Unknown",
                "character": person.get("character") or "",
                "profile": poster_url(person.get("profile_path"), size="w185"),
            }
        )

    similar = [
        _normalize_list_item(m)
        for m in ((detail.get("similar") or {}).get("results") or [])[:12]
    ]

    return {
        "id": detail["id"],
        "title": detail.get("title") or "Untitled",
        "overview": detail.get("overview") or "",
        "release_date": detail.get("release_date") or "",
        "year": year_of(detail.get("release_date")),
        "vote_average": round(float(detail.get("vote_average") or 0), 1),
        "vote_count": detail.get("vote_count") or 0,
        "runtime": detail.get("runtime"),
        "genres": detail.get("genres") or [],
        "poster": poster,
        "poster_srcset": poster_srcset(poster_path),
        "backdrop": backdrop,
        "backdrop_srcset": backdrop_srcset(detail.get("backdrop_path")),
        "fallback_poster": PLACEHOLDER_POSTER,
        "trailer_key": _pick_trailer(videos),
        "trailer_keys": _all_trailer_keys(videos),
        "providers": [],
        "watch_link": None,
        "tagline": detail.get("tagline") or "",
        "cast": cast,
        "similar": similar,
        "original_language": detail.get("original_language") or "",
        "status": detail.get("status") or "",
    }


def genre_name(genre_id: int) -> str:
    for g in get_genres():
        if g["id"] == genre_id:
            return g["name"]
    return "Movies"
