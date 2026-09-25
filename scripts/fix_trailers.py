"""Re-fetch valid official trailer keys; drop false positives like mobile-web-."""

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
FALSE_POS = {"mobile-web-", "youtube-noc", "watch?v=htt", "application"}


def looks_like_id(key: str | None) -> bool:
    if not key or not re.fullmatch(r"[A-Za-z0-9_-]{11}", key):
        return False
    if key.lower() in FALSE_POS:
        return False
    # reject mostly-alpha dictionary-ish tokens with hyphens
    if key.count("-") >= 2 and sum(c.isalpha() for c in key) >= 8:
        return False
    return True


def youtube_exists(key: str) -> bool:
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


def from_tmdb_videos(movie_id: int) -> str | None:
    url = f"https://www.themoviedb.org/movie/{movie_id}/videos?active_nav_item=Trailers"
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            return None
        # TMDB often stores youtube keys in data attributes / card links
        keys = re.findall(r"/video/youtube/([A-Za-z0-9_-]{11})", r.text)
        keys += re.findall(r"youtube\.com/embed/([A-Za-z0-9_-]{11})", r.text)
        keys += re.findall(r"youtu\.be/([A-Za-z0-9_-]{11})", r.text)
        for k in keys:
            if looks_like_id(k) and youtube_exists(k):
                return k
    except Exception:
        return None
    return None


def from_youtube_search(title: str, year: int | None) -> str | None:
    q = f"{title} {year or ''} official trailer".strip()
    try:
        r = requests.get(
            "https://www.youtube.com/results",
            params={"search_query": q},
            headers=HEADERS,
            timeout=25,
        )
        if r.status_code != 200:
            return None
        # ytInitialData videoIds
        keys = re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', r.text)
        for k in keys[:8]:
            if looks_like_id(k) and youtube_exists(k):
                return k
    except Exception:
        return None
    return None


def clean_title(title: str) -> str:
    title = re.sub(r"\s*[—\-]\s*The Movie Database.*$", "", title, flags=re.I)
    title = title.replace("&#39;", "'").replace("&quot;", '"').replace("&amp;", "&")
    title = re.sub(r"<[^>]+>", "", title)
    return title.strip()


def main():
    rows = json.loads(CATALOG.read_text(encoding="utf-8"))
    need = []
    for r in rows:
        if not r.get("id"):
            continue
        if r.get("title"):
            r["title"] = clean_title(r["title"])
        key = r.get("trailer_key")
        if not looks_like_id(key) or not youtube_exists(key or ""):
            r["trailer_key"] = None
            need.append(r)
    print(f"need valid trailers: {len(need)}", flush=True)
    fixed = 0
    for i, r in enumerate(need, 1):
        title = r.get("title") or r.get("query") or ""
        key = from_tmdb_videos(r["id"]) or from_youtube_search(title, r.get("year"))
        if key:
            r["trailer_key"] = key
            fixed += 1
            print(f"[{i}/{len(need)}] {title} -> {key}", flush=True)
        else:
            print(f"[{i}/{len(need)}] MISS {title}", flush=True)
        if i % 10 == 0:
            CATALOG.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(0.2)
    CATALOG.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    valid = sum(1 for r in rows if looks_like_id(r.get("trailer_key")))
    print(f"DONE fixed={fixed} valid={valid}/{len(rows)}", flush=True)


if __name__ == "__main__":
    main()
