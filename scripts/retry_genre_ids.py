"""Retry genre_ids for catalog rows that are still missing them."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "year_catalog.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
GENRE_RE = re.compile(r'href="/genre/(\d+)-[^"]+/movie"')


def fetch_genres(movie_id: int) -> list[int]:
    url = f"https://www.themoviedb.org/movie/{movie_id}"
    r = requests.get(url, headers=HEADERS, timeout=25)
    if r.status_code != 200:
        return []
    ids = []
    seen = set()
    for m in GENRE_RE.finditer(r.text):
        gid = int(m.group(1))
        if gid not in seen:
            seen.add(gid)
            ids.append(gid)
    return ids


def main() -> None:
    rows = json.loads(OUT.read_text(encoding="utf-8"))
    need = [r for r in rows if r.get("id") and not r.get("genre_ids")]
    print(f"retrying {len(need)} missing", flush=True)
    for i, row in enumerate(need, 1):
        gids = fetch_genres(int(row["id"]))
        if gids:
            row["genre_ids"] = gids
        if i % 25 == 0 or i == len(need):
            print(f"[{i}/{len(need)}] {row.get('title')} -> {gids}", flush=True)
            OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(0.35)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with_g = sum(1 for r in rows if r.get("genre_ids"))
    print(f"done — {with_g}/{len(rows)} have genre_ids", flush=True)


if __name__ == "__main__":
    main()
