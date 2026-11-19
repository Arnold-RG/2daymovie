"""Resolve curated TV series to TMDB metadata (posters + official trailer keys)."""

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

from data.series_shows import SERIES_SHOWS  # noqa: E402

OUT = ROOT / "data" / "series_catalog.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
YT_KEY = re.compile(r"^[A-Za-z0-9_-]{11}$")


def looks_like_youtube_key(key: str | None) -> bool:
    if not key or not YT_KEY.fullmatch(key):
        return False
    if key.startswith("mobile") or key.endswith("-") or "web-" in key:
        return False
    return True


def oembed_ok(key: str) -> bool:
    try:
        r = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={key}", "format": "json"},
            headers=HEADERS,
            timeout=15,
        )
        return r.status_code == 200
    except Exception:
        return False


def search_tv(title: str, year: int) -> dict | None:
    url = f"https://www.themoviedb.org/search/tv?query={quote_plus(title)}"
    r = requests.get(url, headers=HEADERS, timeout=25)
    if r.status_code != 200:
        return None
    html = r.text
    candidates = []
    for m in re.finditer(r"/tv/(\d+)[^\"']*[\"'].{0,500}?(\d{4})", html, re.S):
        tid = int(m.group(1))
        y = int(m.group(2))
        if y < 1980 or y > 2035:
            continue
        candidates.append((abs(y - year), y, tid))
    if not candidates:
        m = re.search(r"/tv/(\d+)", html)
        if not m:
            return None
        return {"id": int(m.group(1)), "year": year}
    best: dict[int, tuple[int, int, int]] = {}
    for item in candidates:
        tid = item[2]
        if tid not in best or item < best[tid]:
            best[tid] = item
    pick = sorted(best.values())[0]
    return {"id": pick[2], "year": pick[1]}


def enrich(tv_id: int) -> dict:
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
    title_m = re.search(r"<title>(.*?)\s*[—(]", html)
    title = title_m.group(1).strip() if title_m else str(tv_id)
    title = re.sub(r"\s*—\s*The Movie Database.*$", "", title).strip()
    ov_m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
    overview = (
        (ov_m.group(1) if ov_m else "")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
    )
    candidates = re.findall(
        r"(?:youtube\.com/(?:embed/|watch\?v=)|youtu\.be/|\"key\":\")([A-Za-z0-9_-]{11})",
        html,
    )
    trailer = None
    for key in candidates:
        if looks_like_youtube_key(key) and oembed_ok(key):
            trailer = key
            break
        time.sleep(0.1)
    return {
        "id": tv_id,
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
            existing = {
                e["query"]: e
                for e in json.loads(OUT.read_text(encoding="utf-8"))
                if e.get("query")
            }
        except Exception:
            existing = {}

    results = []
    total = len(SERIES_SHOWS)
    for i, show in enumerate(SERIES_SHOWS, 1):
        title = show["title"]
        year = int(show["start"])
        if title in existing and existing[title].get("id") and existing[title].get("poster_path"):
            row = existing[title]
            row["start"] = show["start"]
            row["end"] = show["end"]
            results.append(row)
            print(f"[{i}/{total}] cache {title}", flush=True)
            continue
        try:
            hit = search_tv(title, year)
            if not hit:
                results.append(
                    {
                        "query": title,
                        "start": show["start"],
                        "end": show["end"],
                        "id": None,
                        "error": "not_found",
                    }
                )
                print(f"[{i}/{total}] MISS {title}", flush=True)
                continue
            meta = enrich(hit["id"])
            row = {
                "query": title,
                "start": show["start"],
                "end": show["end"],
                "id": meta["id"],
                "title": meta["title"] or title,
                "overview": meta["overview"],
                "poster_path": meta["poster_path"],
                "backdrop_path": meta["backdrop_path"],
                "trailer_key": meta["trailer_key"],
                "watch_link": f"https://www.themoviedb.org/tv/{meta['id']}/watch",
                "vote_average": 0,
            }
            results.append(row)
            print(
                f"[{i}/{total}] OK {title} -> {meta['id']} trailer={bool(meta['trailer_key'])}",
                flush=True,
            )
            time.sleep(0.35)
        except Exception as exc:
            results.append(
                {
                    "query": title,
                    "start": show["start"],
                    "end": show["end"],
                    "id": None,
                    "error": str(exc),
                }
            )
            print(f"[{i}/{total}] ERR {title}: {exc}", flush=True)
            time.sleep(0.5)
        if i % 8 == 0:
            OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r.get("id"))
    trailers = sum(1 for r in results if r.get("trailer_key"))
    print(f"DONE ok={ok}/{total} trailers={trailers}", flush=True)


if __name__ == "__main__":
    main()
