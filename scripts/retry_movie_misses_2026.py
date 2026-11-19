"""Retry unresolved / wrong 2026 movie matches."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import quote_plus

import requests

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "year_catalog.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Force-clear known bad matches then retry
CLEAR = {"Hexe", "Ramayana: Part 1"}

ALT = {
    "Digger": ["Digger Tom Cruise", "Digger 2026"],
    "Clayface": ["Clayface movie", "Clayface 2026"],
    "Street Fighter": ["Street Fighter movie 2026", "Street Fighter Legendary"],
    "Wildwood": ["Wildwood Laika", "Wildwood 2026"],
    "Whalefall": ["Whale Fall", "Whalefall movie"],
    "Klara and the Sun": ["Klara and the Sun movie", "Klara and the Sun 2026"],
    "Hope": ["Hope 2026 movie"],
    "The Beast": ["The Beast 2026 movie"],
    "Other Mommy": ["Other Mommy 2026", "The Other Mommy"],
    "The Hunger Games: Sunrise on the Reaping": [
        "Sunrise on the Reaping",
        "Hunger Games Sunrise",
    ],
    "Ramayana: Part 1": ["Ramayana Part One", "Ramayana 2026"],
    "Hexe": ["Hexe Disney", "Hexe animated"],
}


def search(title: str, year: int = 2026) -> int | None:
    url = f"https://www.themoviedb.org/search/movie?query={quote_plus(title)}"
    r = requests.get(url, headers=HEADERS, timeout=25)
    if r.status_code != 200:
        return None
    html = r.text
    candidates = []
    for m in re.finditer(r"/movie/(\d+)[^\"']*[\"'].{0,500}?(\d{4})", html, re.S):
        mid = int(m.group(1))
        y = int(m.group(2))
        if 2018 <= y <= 2030:
            candidates.append((abs(y - year), y, mid))
    if candidates:
        return sorted(candidates)[0][2]
    m = re.search(r"/movie/(\d+)", html)
    return int(m.group(1)) if m else None


def enrich(mid: int) -> dict:
    r = requests.get(f"https://www.themoviedb.org/movie/{mid}", headers=HEADERS, timeout=25)
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
    tm = re.search(r"<title>(.*?)\s*[—(]", html)
    title = (tm.group(1).strip() if tm else str(mid))
    title = re.sub(r"\s*—\s*The Movie Database.*$", "", title).strip()
    ov = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
    overview = (
        (ov.group(1) if ov else "")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
    )[:700]
    return {
        "id": mid,
        "title": title,
        "overview": overview,
        "poster_path": poster,
        "backdrop_path": backdrop or poster,
    }


def main() -> None:
    rows = json.loads(CATALOG.read_text(encoding="utf-8"))
    byq = {r.get("query"): r for r in rows}
    for q in CLEAR:
        row = byq.get(q)
        if row:
            row["id"] = None
            row["title"] = None
            row["poster_path"] = None
            row["backdrop_path"] = None
            row["trailer_key"] = None
            print("cleared", q, flush=True)

    for query, alts in ALT.items():
        row = byq.get(query)
        if not row:
            continue
        if row.get("id") and query not in CLEAR:
            print("skip", query, flush=True)
            continue
        hit = None
        for q in [query, *alts]:
            hit = search(q)
            print(f" try {q} -> {hit}", flush=True)
            if hit:
                break
            time.sleep(0.3)
        if not hit:
            print("MISS", query, flush=True)
            continue
        meta = enrich(hit)
        # reject obvious wrong anime Hexe
        if query == "Hexe" and "VOTOMS" in (meta.get("title") or ""):
            print("reject bad Hexe match", flush=True)
            continue
        if query.startswith("Ramayana") and "Part Two" in (meta.get("title") or ""):
            print("reject Ramayana Part Two", flush=True)
            continue
        row.update(
            {
                "year": 2026,
                "query": query,
                "id": meta["id"],
                "title": meta["title"] or query,
                "overview": meta["overview"],
                "poster_path": meta["poster_path"],
                "backdrop_path": meta["backdrop_path"],
                "watch_link": f"https://www.themoviedb.org/movie/{meta['id']}/watch",
                "vote_average": 0,
                "release_date": "2026-01-01",
            }
        )
        print(f"OK {query} -> {meta['id']} {meta['title']}", flush=True)
        time.sleep(0.35)

    CATALOG.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("done", flush=True)


if __name__ == "__main__":
    main()
