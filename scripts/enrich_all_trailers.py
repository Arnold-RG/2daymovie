"""Collect ALL official YouTube trailer keys per catalog title from TMDB videos pages."""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
YEAR_OUT = ROOT / "data" / "year_catalog.json"
SERIES_OUT = ROOT / "data" / "series_catalog.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
DATA_ID_RE = re.compile(r'data-id="([A-Za-z0-9_-]{11})"')
YT_RE = re.compile(r"(?:youtube\.com/embed/|youtu\.be/)([A-Za-z0-9_-]{11})")


def _valid(key: str) -> bool:
    if not key or len(key) != 11:
        return False
    if key.startswith("mobile") or "web-" in key or key.endswith("-"):
        return False
    return True


def fetch_keys(kind: str, media_id: int) -> list[str]:
    url = f"https://www.themoviedb.org/{kind}/{media_id}/videos"
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            return []
        keys: list[str] = []
        seen: set[str] = set()
        for key in DATA_ID_RE.findall(r.text) + YT_RE.findall(r.text):
            if not _valid(key) or key in seen:
                continue
            seen.add(key)
            keys.append(key)
        return keys[:12]
    except Exception:
        return []


def enrich_file(path: Path, kind: str) -> None:
    rows = json.loads(path.read_text(encoding="utf-8"))
    for i, row in enumerate(rows, 1):
        mid = row.get("id")
        if not mid:
            continue
        existing = []
        if row.get("trailer_keys"):
            existing = [k for k in row["trailer_keys"] if _valid(k)]
        elif row.get("trailer_key") and _valid(row["trailer_key"]):
            existing = [row["trailer_key"]]

        # Always refresh from TMDB videos page to collect multiples
        keys = fetch_keys(kind, int(mid))
        time.sleep(0.28)
        if not keys and existing:
            keys = existing
        if not keys:
            print(f"[{i}/{len(rows)}] NO KEYS {row.get('title') or row.get('query')}", flush=True)
            row["trailer_key"] = None
            row["trailer_keys"] = []
            continue
        # Prefer keeping prior primary first if still present
        primary = row.get("trailer_key")
        if primary in keys:
            keys = [primary] + [k for k in keys if k != primary]
        row["trailer_keys"] = keys
        row["trailer_key"] = keys[0]
        if i % 20 == 0 or len(keys) > 1:
            print(
                f"[{i}/{len(rows)}] {row.get('title') or row.get('query')} -> {len(keys)} trailers",
                flush=True,
            )
        if i % 40 == 0:
            path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    # Drop rows with no trailers
    kept = [r for r in rows if r.get("trailer_key")]
    path.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
    multi = sum(1 for r in kept if len(r.get("trailer_keys") or []) > 1)
    print(f"{path.name}: {len(kept)} titles, {multi} with multiple trailers", flush=True)


def main() -> None:
    enrich_file(YEAR_OUT, "movie")
    enrich_file(SERIES_OUT, "tv")


if __name__ == "__main__":
    main()
