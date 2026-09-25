"""Fill missing official trailer YouTube keys for series_catalog.json."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "series_catalog.json"
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


def find_trailer(tv_id: int, title: str, year: int | None) -> str | None:
    urls = [
        f"https://www.themoviedb.org/tv/{tv_id}/videos",
        f"https://www.themoviedb.org/tv/{tv_id}",
    ]
    candidates: list[str] = []
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
            if r.status_code != 200:
                continue
            for m in re.finditer(
                r"(?:Official\s+)?Trailer[\s\S]{0,180}?([A-Za-z0-9_-]{11})",
                r.text,
                re.I,
            ):
                candidates.append(m.group(1))
            for m in re.finditer(
                r"(?:youtube\.com/(?:embed/|watch\?v=)|youtu\.be/|\"key\":\")([A-Za-z0-9_-]{11})",
                r.text,
            ):
                candidates.append(m.group(1))
        except Exception:
            continue

    seen: set[str] = set()
    for key in candidates:
        if key in seen or not looks_like_youtube_key(key):
            continue
        seen.add(key)
        if oembed_ok(key):
            return key
        time.sleep(0.12)
    return None


def main():
    rows = json.loads(CATALOG.read_text(encoding="utf-8"))
    for row in rows:
        if not looks_like_youtube_key(row.get("trailer_key")):
            row["trailer_key"] = None

    missing = [r for r in rows if r.get("id") and not r.get("trailer_key")]
    print(f"need trailers for {len(missing)} / {len(rows)}", flush=True)
    filled = 0
    for i, row in enumerate(missing, 1):
        key = find_trailer(
            row["id"], row.get("title") or row.get("query") or "", row.get("start")
        )
        if key:
            row["trailer_key"] = key
            filled += 1
            print(f"[{i}/{len(missing)}] {row.get('title')} -> {key}", flush=True)
        else:
            print(f"[{i}/{len(missing)}] MISS {row.get('title')}", flush=True)
        if i % 10 == 0:
            CATALOG.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        time.sleep(0.2)
    CATALOG.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(1 for r in rows if r.get("trailer_key"))
    print(f"DONE filled={filled} total_with_trailer={total}", flush=True)


if __name__ == "__main__":
    main()
