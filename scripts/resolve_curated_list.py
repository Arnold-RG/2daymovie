"""Resolve only missing curated titles into year_catalog.json / series_catalog.json."""

from __future__ import annotations

import json
import html
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.year_movies import YEAR_MOVIES  # noqa: E402
from data.series_shows import SERIES_SHOWS  # noqa: E402

YEAR_OUT = ROOT / "data" / "year_catalog.json"
SERIES_OUT = ROOT / "data" / "series_catalog.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
YT_RE = re.compile(r"(?:youtube\.com/embed/|youtu\.be/)([A-Za-z0-9_-]{11})")
DATA_ID_RE = re.compile(r'data-id="([A-Za-z0-9_-]{11})"')
GENRE_RE = re.compile(r'href="/genre/(\d+)-[^"]+/movie"')


def _norm(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (title or "").lower())


def _pick_trailer(html: str) -> str | None:
    keys = DATA_ID_RE.findall(html) + YT_RE.findall(html)
    for key in keys:
        if key.startswith("mobile") or "web-" in key:
            continue
        return key
    return None


def search_movie(title: str, year: int) -> int | None:
    url = f"https://www.themoviedb.org/search/movie?query={quote_plus(title)}"
    r = requests.get(url, headers=HEADERS, timeout=25)
    if r.status_code != 200:
        return None
    html = r.text
    candidates = []
    for m in re.finditer(r"/movie/(\d+)[^\"']*[\"'].{0,500}?(\d{4})", html, re.S):
        mid = int(m.group(1))
        y = int(m.group(2))
        if 1900 <= y <= 2035:
            candidates.append((abs(y - year), y, mid))
    if not candidates:
        m = re.search(r"/movie/(\d+)", html)
        return int(m.group(1)) if m else None
    best: dict[int, tuple[int, int, int]] = {}
    for item in candidates:
        mid = item[2]
        if mid not in best or item < best[mid]:
            best[mid] = item
    return sorted(best.values())[0][2]


def search_tv(title: str) -> int | None:
    url = f"https://www.themoviedb.org/search/tv?query={quote_plus(title)}"
    r = requests.get(url, headers=HEADERS, timeout=25)
    if r.status_code != 200:
        return None
    m = re.search(r"/tv/(\d+)", r.text)
    return int(m.group(1)) if m else None


def enrich_movie(movie_id: int) -> dict:
    url = f"https://www.themoviedb.org/movie/{movie_id}"
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    html = r.text
    ogs = re.findall(r'property="og:image" content="([^"]+)"', html)
    poster = backdrop = None
    for u in ogs:
        m = re.search(r"/t/p/w\d+(/[A-Za-z0-9_]+\.jpg)", u)
        if not m:
            continue
        path = m.group(1)
        if "/w500/" in u or "/w342/" in u:
            poster = path
        if "/w780/" in u or "/w1280/" in u:
            backdrop = path
    title_m = re.search(r"<title>(.*?)\s*\(", html)
    title = html.unescape(title_m.group(1).strip() if title_m else str(movie_id))
    ov_m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
    overview = html.unescape(
        (ov_m.group(1) if ov_m else "")
    )
    trailer = _pick_trailer(html)
    if not trailer:
        vr = requests.get(f"{url}/videos", headers=HEADERS, timeout=25)
        if vr.status_code == 200:
            trailer = _pick_trailer(vr.text)
    genres = []
    seen = set()
    for m in GENRE_RE.finditer(html):
        gid = int(m.group(1))
        if gid not in seen:
            seen.add(gid)
            genres.append(gid)
    return {
        "id": movie_id,
        "title": title,
        "overview": overview[:700],
        "poster_path": poster,
        "backdrop_path": backdrop or poster,
        "trailer_key": trailer,
        "genre_ids": genres,
        "watch_link": f"https://www.themoviedb.org/movie/{movie_id}/watch",
    }


def enrich_tv(tv_id: int) -> dict:
    url = f"https://www.themoviedb.org/tv/{tv_id}"
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    html = r.text
    ogs = re.findall(r'property="og:image" content="([^"]+)"', html)
    poster = backdrop = None
    for u in ogs:
        m = re.search(r"/t/p/w\d+(/[A-Za-z0-9_]+\.jpg)", u)
        if not m:
            continue
        path = m.group(1)
        if "/w500/" in u or "/w342/" in u:
            poster = path
        if "/w780/" in u or "/w1280/" in u:
            backdrop = path
    title_m = re.search(r"<title>(.*?)\s*\(", html)
    title = title_m.group(1).strip() if title_m else str(tv_id)
    ov_m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
    overview = (
        (ov_m.group(1) if ov_m else "")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
    )
    trailer = _pick_trailer(html)
    if not trailer:
        vr = requests.get(f"{url}/videos", headers=HEADERS, timeout=25)
        if vr.status_code == 200:
            trailer = _pick_trailer(vr.text)
    return {
        "id": tv_id,
        "title": title,
        "overview": overview[:700],
        "poster_path": poster,
        "backdrop_path": backdrop or poster,
        "trailer_key": trailer,
        "watch_link": f"https://www.themoviedb.org/tv/{tv_id}/watch",
    }


def resolve_movies() -> None:
    existing = []
    if YEAR_OUT.exists():
        existing = json.loads(YEAR_OUT.read_text(encoding="utf-8"))
    by_key = {f"{r.get('year')}|{_norm(r.get('query'))}": r for r in existing if r.get("query")}
    by_title_year = {
        f"{r.get('year')}|{_norm(r.get('title'))}": r for r in existing
    }
    by_any = {}
    for r in existing:
        if not r.get("trailer_key"):
            continue
        by_any[_norm(r.get("query"))] = r
        by_any[_norm(r.get("title"))] = r

    planned = []
    for year, titles in YEAR_MOVIES.items():
        for title in titles:
            planned.append((year, title))

    results = []
    for i, (year, title) in enumerate(planned, 1):
        n = _norm(title)
        row = by_key.get(f"{year}|{n}") or by_title_year.get(f"{year}|{n}") or by_any.get(n)
        if row and row.get("id") and row.get("trailer_key"):
            out = dict(row)
            out["year"] = year
            out["query"] = title
            results.append(out)
            continue
        print(f"[{i}/{len(planned)}] resolve {year} {title}", flush=True)
        try:
            mid = search_movie(title, year)
            time.sleep(0.3)
            if not mid:
                print(f"  MISS {title}", flush=True)
                continue
            meta = enrich_movie(mid)
            time.sleep(0.3)
            if not meta.get("trailer_key"):
                print(f"  NO TRAILER {title} -> {mid}", flush=True)
                continue
            results.append(
                {
                    "year": year,
                    "query": title,
                    "id": meta["id"],
                    "title": meta["title"],
                    "overview": meta["overview"],
                    "poster_path": meta["poster_path"],
                    "backdrop_path": meta["backdrop_path"],
                    "trailer_key": meta["trailer_key"],
                    "release_date": f"{year}-01-01",
                    "vote_average": (row or {}).get("vote_average", 0),
                    "watch_link": meta["watch_link"],
                    "genre_ids": meta.get("genre_ids") or [],
                }
            )
            print(f"  OK {meta['title']} trailer={meta['trailer_key']}", flush=True)
        except Exception as exc:
            print(f"  ERR {title}: {exc}", flush=True)
        if i % 25 == 0:
            YEAR_OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    YEAR_OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"movies catalog: {len(results)}/{len(planned)} with trailers", flush=True)


def resolve_series() -> None:
    existing = []
    if SERIES_OUT.exists():
        existing = json.loads(SERIES_OUT.read_text(encoding="utf-8"))
    by_query = {r.get("query"): r for r in existing if r.get("query")}

    results = []
    for i, planned in enumerate(SERIES_SHOWS, 1):
        title = planned["title"]
        row = by_query.get(title)
        if row and row.get("id") and row.get("trailer_key"):
            out = dict(row)
            out["query"] = title
            out["start"] = planned["start"]
            out["end"] = planned.get("end")
            results.append(out)
            continue
        print(f"[{i}/{len(SERIES_SHOWS)}] resolve series {title}", flush=True)
        try:
            tid = search_tv(title)
            time.sleep(0.35)
            if not tid:
                print(f"  MISS {title}", flush=True)
                continue
            meta = enrich_tv(tid)
            time.sleep(0.35)
            if not meta.get("trailer_key"):
                print(f"  NO TRAILER {title} -> {tid}", flush=True)
                continue
            results.append(
                {
                    "query": title,
                    "id": meta["id"],
                    "title": meta["title"],
                    "overview": meta["overview"],
                    "poster_path": meta["poster_path"],
                    "backdrop_path": meta["backdrop_path"],
                    "trailer_key": meta["trailer_key"],
                    "start": planned["start"],
                    "end": planned.get("end"),
                    "vote_average": row.get("vote_average", 0) if row else 0,
                    "watch_link": meta["watch_link"],
                }
            )
            print(f"  OK {meta['title']}", flush=True)
        except Exception as exc:
            print(f"  ERR {title}: {exc}", flush=True)

    SERIES_OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"series catalog: {len(results)}/{len(SERIES_SHOWS)} with trailers", flush=True)


if __name__ == "__main__":
    resolve_movies()
    resolve_series()
