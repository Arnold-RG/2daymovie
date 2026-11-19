"""Attach TMDB genre_ids to year_catalog.json via public movie pages."""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "year_catalog.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
GENRE_RE = re.compile(r"/genre/(\d+)-[a-z0-9-]+(?:/movie)?", re.I)


def fetch_genres(movie_id: int) -> list[int]:
    url = f"https://www.themoviedb.org/movie/{movie_id}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return []
        ids = []
        seen = set()
        for m in GENRE_RE.finditer(r.text):
            gid = int(m.group(1))
            if gid in seen or gid == 0:
                continue
            # TMDB Adult genre id is 0 historically; modern Adult is filtered elsewhere
            seen.add(gid)
            ids.append(gid)
        return ids[:8]
    except Exception:
        return []


def main() -> None:
    rows = json.loads(OUT.read_text(encoding="utf-8"))
    need = [r for r in rows if r.get("id") and not r.get("genre_ids")]
    print(f"need genres for {len(need)} / {len(rows)}", flush=True)
    if not need:
        return

    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_genres, int(r["id"])): r for r in need}
        for fut in as_completed(futures):
            row = futures[fut]
            gids = fut.result()
            if gids:
                row["genre_ids"] = gids
            done += 1
            if done % 50 == 0 or done == len(need):
                print(f"[{done}/{len(need)}] last={row.get('title')} genres={gids}", flush=True)
            time.sleep(0.02)

    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with_g = sum(1 for r in rows if r.get("genre_ids"))
    print(f"done — {with_g}/{len(rows)} have genre_ids", flush=True)


if __name__ == "__main__":
    main()
