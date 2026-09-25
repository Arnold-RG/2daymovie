"""Resolve curated year titles to TMDB metadata (posters + official trailer keys)."""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.year_movies import YEAR_MOVIES  # noqa: E402

OUT = ROOT / "data" / "year_catalog.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def search_movie(title: str, year: int) -> dict | None:
    url = f"https://www.themoviedb.org/search/movie?query={quote_plus(title)}"
    r = requests.get(url, headers=HEADERS, timeout=25)
    if r.status_code != 200:
        return None
    html = r.text
    candidates = []
    for m in re.finditer(r"/movie/(\d+)[^\"']*[\"'].{0,500}?(\d{4})", html, re.S):
        mid = int(m.group(1))
        y = int(m.group(2))
        if y < 1900 or y > 2035:
            continue
        candidates.append((abs(y - year), y, mid))
    if not candidates:
        m = re.search(r"/movie/(\d+)", html)
        if not m:
            return None
        return {"id": int(m.group(1)), "year": year}
    # Prefer exact year, then nearest; de-dupe by id keeping best score
    best: dict[int, tuple[int, int, int]] = {}
    for item in candidates:
        mid = item[2]
        if mid not in best or item < best[mid]:
            best[mid] = item
    ranked = sorted(best.values())
    pick = ranked[0]
    return {"id": pick[2], "year": pick[1]}


def enrich(movie_id: int) -> dict:
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
    title = title_m.group(1).strip() if title_m else str(movie_id)
    ov_m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
    overview = (ov_m.group(1) if ov_m else "").replace("&#39;", "'").replace("&quot;", '"').replace("&amp;", "&")
    # YouTube trailer embeds / links
    yt = re.findall(r"(?:youtube\.com/embed/|youtu\.be/)([A-Za-z0-9_-]{6,})", html)
    trailer = yt[0] if yt else None
    return {
        "id": movie_id,
        "title": title,
        "overview": overview[:700],
        "poster_path": poster,
        "backdrop_path": backdrop or poster,
        "trailer_key": trailer,
    }


def main():
    existing = {}
    if OUT.exists():
        try:
            existing = {f"{e['year']}|{e['query']}": e for e in json.loads(OUT.read_text(encoding="utf-8"))}
        except Exception:
            existing = {}

    results = []
    total = sum(len(v) for v in YEAR_MOVIES.values())
    done = 0
    for year, titles in YEAR_MOVIES.items():
        for title in titles:
            done += 1
            key = f"{year}|{title}"
            if key in existing and existing[key].get("id") and existing[key].get("poster_path"):
                results.append(existing[key])
                print(f"[{done}/{total}] cache {year} {title}", flush=True)
                continue
            try:
                hit = search_movie(title, year)
                if not hit:
                    results.append({"year": year, "query": title, "id": None, "error": "not_found"})
                    print(f"[{done}/{total}] MISS {year} {title}", flush=True)
                    continue
                meta = enrich(hit["id"])
                row = {
                    "year": year,
                    "query": title,
                    "id": meta["id"],
                    "title": meta["title"] or title,
                    "overview": meta["overview"],
                    "poster_path": meta["poster_path"],
                    "backdrop_path": meta["backdrop_path"],
                    "trailer_key": meta["trailer_key"],
                    "release_date": f"{year}-01-01",
                    "vote_average": 0,
                    "watch_link": f"https://www.themoviedb.org/movie/{meta['id']}/watch",
                }
                results.append(row)
                print(f"[{done}/{total}] OK {year} {title} -> {meta['id']} trailer={bool(meta['trailer_key'])}", flush=True)
                time.sleep(0.35)
            except Exception as exc:
                results.append({"year": year, "query": title, "id": None, "error": str(exc)})
                print(f"[{done}/{total}] ERR {year} {title}: {exc}", flush=True)
                time.sleep(0.5)
            # checkpoint
            if done % 10 == 0:
                OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r.get("id"))
    trailers = sum(1 for r in results if r.get("trailer_key"))
    print(f"DONE ok={ok}/{total} trailers={trailers}", flush=True)


if __name__ == "__main__":
    main()
