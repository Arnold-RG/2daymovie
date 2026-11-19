"""Retry unresolved upcoming series with alternate TMDB search queries."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import quote_plus

import requests

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "series_catalog.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

ALT = {
    "Carrie": ["Carrie Flanagan", "Carrie Amazon"],
    "Crystal Lake": ["Crystal Lake Friday the 13th", "Crystal Lake series"],
    "Lanterns": ["Lanterns HBO", "Lanterns DC"],
    "Pride & Prejudice": ["Pride and Prejudice Netflix", "Pride & Prejudice 2026"],
    "Tip Toe": ["Tip Toe Alan Cumming", "Tiptoe Russell T Davies"],
    "VisionQuest": ["VisionQuest Marvel", "Vision Quest Disney+"],
    "Widow's Bay": ["Widows Bay", "Widow's Bay series"],
    "Wonder Man": ["Wonder Man Marvel", "Wonder Man Disney+"],
}


def search(q: str) -> int | None:
    r = requests.get(
        f"https://www.themoviedb.org/search/tv?query={quote_plus(q)}",
        headers=HEADERS,
        timeout=25,
    )
    if r.status_code != 200:
        return None
    m = re.search(r"/tv/(\d+)", r.text)
    return int(m.group(1)) if m else None


def enrich(tid: int) -> dict:
    r = requests.get(f"https://www.themoviedb.org/tv/{tid}", headers=HEADERS, timeout=25)
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
    title = (tm.group(1).strip() if tm else str(tid))
    title = re.sub(r"\s*—\s*The Movie Database.*$", "", title).strip()
    ov = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
    overview = (
        (ov.group(1) if ov else "")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
        .replace("&amp;", "&")
    )[:700]
    return {
        "id": tid,
        "title": title,
        "overview": overview,
        "poster_path": poster,
        "backdrop_path": backdrop or poster,
    }


def main() -> None:
    rows = json.loads(CATALOG.read_text(encoding="utf-8"))
    byq = {r.get("query"): r for r in rows}
    for query, alts in ALT.items():
        row = byq.get(query)
        if not row or row.get("id"):
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
        row.update(
            {
                "id": meta["id"],
                "title": meta["title"] or query,
                "overview": meta["overview"],
                "poster_path": meta["poster_path"],
                "backdrop_path": meta["backdrop_path"],
                "watch_link": f"https://www.themoviedb.org/tv/{meta['id']}/watch",
                "vote_average": 0,
            }
        )
        print(f"OK {query} -> {meta['id']} {meta['title']}", flush=True)
        time.sleep(0.35)
    CATALOG.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ids", sum(1 for r in rows if r.get("id")), flush=True)


if __name__ == "__main__":
    main()
