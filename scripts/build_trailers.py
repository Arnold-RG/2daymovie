#!/usr/bin/env python3
"""Verify the curated upcoming-trailer list and write data/trailers.json.

Only official trailers uploaded by the studio / distributor channel are allowed.
Each entry is re-checked with yt-dlp: it must exist, be public, embeddable,
not age-restricted, and still be uploaded by the expected official channel.
Films whose release date has passed are dropped automatically.

    python scripts/build_trailers.py
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "trailers.json"

# film, release date, YouTube id, official uploader channel id
CURATED = [
    ("Avengers: Doomsday", "2026-12-18", "irVNGjRFZGk", "UCvC4D8onUfXzvjTOM-dBfEA"),  # Marvel Entertainment
    ("Dune: Part Three", "2026-12-18", "uJqaGLmZpGo", "UCjmJDM5pRKbUlVIzDYYWb6g"),  # Warner Bros.
    ("Jumanji: Open World", "2026-12-25", "nIw1O3zvOfE", "UCz97F7dMxBNOfGYu3rx8aCw"),  # Sony Pictures
    ("Hexed", "2026-11-25", "KXO21xZdUaM", "UC_976xMxPgzIa290Hqtk-9g"),  # Walt Disney Animation Studios
    ("The Angry Birds Movie 3", "2026-12-23", "FjYzudbOzlY", "UCF9imwPMSGz4Vq1NiTWCC7g"),  # Paramount Pictures
    ("Violent Night 2", "2026-12-04", "FmM2giDwLAE", "UCq0OueAsdxH6b8nyAspwViw"),  # Universal Pictures
    ("Ice Age: Boiling Point", "2027-02-05", "e67Qtn_3hkc", "UC_5niPa-d35gg88HaS7RrIw"),  # Disney
    ("Narnia: The Magician's Nephew", "2027-02-12", "gDJ-ini7fF0", "UCWOA1ZGywLbqmigxE4Qlvuw"),  # Netflix
    ("Gatto", "2027-03-05", "fq7Q-dtIZeM", "UC_IRYSp4auq7hKLvziWVH6w"),  # Pixar
]


def info(vid: str) -> dict | None:
    p = subprocess.run([sys.executable, "-m", "yt_dlp", "--no-warnings", "-j", "--skip-download",
                        f"https://www.youtube.com/watch?v={vid}"], capture_output=True, text=True, timeout=120)
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return None


def main() -> int:
    today = dt.date.today().isoformat()
    out = []
    for film, release, vid, channel_id in CURATED:
        if release <= today:
            print(f"skip {film}: already released", file=sys.stderr)
            continue
        d = info(vid)
        if not d or not d.get("playable_in_embed") or (d.get("age_limit") or 0) or d.get("channel_id") != channel_id:
            print(f"skip {film}: not verified ({vid})", file=sys.stderr)
            continue
        # schema: { title, release_date, youtube_id, start, end } (start/end = muted header clip, seconds)
        start = 6
        out.append({"title": film, "release_date": release, "youtube_id": vid,
                    "start": start, "end": min(int(d["duration"]), start + 32)})
    out.sort(key=lambda t: (t["title"] != "Avengers: Doomsday", t["release_date"]))
    OUT.write_text(json.dumps({"generated": today, "items": out}, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(out)} trailers", file=sys.stderr)
    return 0 if out else 1


if __name__ == "__main__":
    raise SystemExit(main())
