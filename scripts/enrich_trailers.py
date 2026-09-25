"""Fill missing official trailer YouTube keys for year_catalog.json."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "year_catalog.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def find_trailer(movie_id: int, title: str, year: int | None) -> str | None:
    # TMDB videos tab / media often includes youtube ids in JSON blobs
    urls = [
        f"https://www.themoviedb.org/movie/{movie_id}/videos",
        f"https://www.themoviedb.org/movie/{movie_id}",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            if r.status_code != 200:
                continue
            keys = re.findall(
                r"(?:youtube\.com/(?:embed/|watch\?v=)|youtu\.be/|\"key\":\")([A-Za-z0-9_-]{11})",
                r.text,
            )
            # Prefer keys near the word Trailer
            trailerish = re.findall(
                r"Trailer[\s\S]{0,120}?([A-Za-z0-9_-]{11})|([A-Za-z0-9_-]{11})[\s\S]{0,120}?Trailer",
                r.text,
                re.I,
            )
            for a, b in trailerish:
                k = a or b
                if k and len(k) == 11:
                    return k
            if keys:
                return keys[0]
        except Exception:
            continue

    # YouTube search page (best-effort)
    q = f"{title} {year or ''} official trailer".strip()
    try:
        r = requests.get(
            "https://www.youtube.com/results",
            params={"search_query": q},
            headers=HEADERS,
            timeout=25,
        )
        if r.status_code == 200:
            m = re.search(r"watch\?v=([A-Za-z0-9_-]{11})", r.text)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def main():
    rows = json.loads(CATALOG.read_text(encoding="utf-8"))
    missing = [r for r in rows if r.get("id") and not r.get("trailer_key")]
    print(f"need trailers for {len(missing)} / {len(rows)}", flush=True)
    filled = 0
    for i, row in enumerate(missing, 1):
        key = find_trailer(row["id"], row.get("title") or row.get("query") or "", row.get("year"))
        if key:
            row["trailer_key"] = key
            filled += 1
            print(f"[{i}/{len(missing)}] {row.get('title')} -> {key}", flush=True)
        else:
            print(f"[{i}/{len(missing)}] MISS {row.get('title')}", flush=True)
        if i % 15 == 0:
            CATALOG.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(0.25)
    CATALOG.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(1 for r in rows if r.get("trailer_key"))
    print(f"DONE filled={filled} total_with_trailer={total}", flush=True)


if __name__ == "__main__":
    main()
