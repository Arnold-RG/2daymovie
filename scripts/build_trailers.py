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

# Theatrical release window shown on the site (inclusive).
WINDOW = ("2026-12-01", "2027-03-31")

# film, release date (US theatrical), YouTube id, official uploader channel id,
# clip start/end in seconds (20-45s of footage, chosen past studio logos and title cards)
CURATED = [
    ("Violent Night 2", "2026-12-04", "FmM2giDwLAE", "UCq0OueAsdxH6b8nyAspwViw", 52, 82),  # Universal Pictures
    ("Behemoth!", "2026-12-04", "I6tMFYT9s7E", "UCor9rW6PgxSQ9vUPWQdnaYQ", 26, 56),  # Searchlight Pictures
    ("Killing Castro", "2026-12-11", "cal1RfsmHUI", "UCJ6nMHaJPZvsJ-HmUmj1SeA", 62, 86),  # Lionsgate
    ("Avengers: Doomsday", "2026-12-18", "irVNGjRFZGk", "UCvC4D8onUfXzvjTOM-dBfEA", 30, 62),  # Marvel Entertainment
    ("Dune: Part Three", "2026-12-18", "uJqaGLmZpGo", "UCjmJDM5pRKbUlVIzDYYWb6g", 24, 56),  # Warner Bros.
    ("The Angry Birds Movie 3", "2026-12-23", "FjYzudbOzlY", "UCF9imwPMSGz4Vq1NiTWCC7g", 14, 46),  # Paramount Pictures
    ("Jumanji: Open World", "2026-12-25", "nIw1O3zvOfE", "UCz97F7dMxBNOfGYu3rx8aCw", 26, 58),  # Sony Pictures
    ("Mr. Irrelevant", "2026-12-25", "cwVE1qf6Ixs", "UCF9imwPMSGz4Vq1NiTWCC7g", 16, 48),  # Paramount Pictures
    ("Werwulf", "2026-12-25", "CL1EFACsWag", "UCU4SM3j_9TNWaSu8KdGV50g", 18, 44),  # Focus Features
    ("Artificial", "2026-12-25", "ufeJbTNq-BI", "UCpy5dRhZd-JbZP4NsrnLt1w", 16, 46),  # NEON (select theaters; wide Jan 8)
    ("Children of Blood and Bone", "2027-01-15", "a20LtkPALYM", "UCF9imwPMSGz4Vq1NiTWCC7g", 54, 88),  # Paramount Pictures
    ("River", "2027-01-15", "ox8lEnsxDag", "UCq0OueAsdxH6b8nyAspwViw", 5, 35),  # Universal Pictures
    ("The Rescue", "2027-01-29", "nzNYomSd5Ls", "UCF9imwPMSGz4Vq1NiTWCC7g", 20, 50),  # Paramount Pictures
    ("Slayground", "2027-01-29", "XsReYk7AqPg", "UCuPivVjnfNo4mb3Oog_frZg", 42, 68),  # A24
    ("Ice Age: Boiling Point", "2027-02-05", "e67Qtn_3hkc", "UC_5niPa-d35gg88HaS7RrIw", 8, 40),  # Disney
    ("Remain", "2027-02-05", "Fso81Ypg9T4", "UCjmJDM5pRKbUlVIzDYYWb6g", 33, 63),  # Warner Bros.
    ("The Comeback King", "2027-02-05", "dlpxXcC8nPk", "UCq0OueAsdxH6b8nyAspwViw", 6, 34),  # Universal Pictures
    ("Narnia: The Magician's Nephew", "2027-02-12", "gDJ-ini7fF0", "UCWOA1ZGywLbqmigxE4Qlvuw", 16, 42),  # Netflix (theatrical)
    ("Gatto", "2027-03-05", "fq7Q-dtIZeM", "UC_IRYSp4auq7hKLvziWVH6w", 33, 63),  # Pixar
    ("The Thomas Crown Affair", "2027-03-05", "A643rogutGM", "UCf5CjDJvsFvtVIhkfmKAwAA", 20, 50),  # Amazon MGM Studios
    ("The Exorcist: Martyrs", "2027-03-12", "iIEYfH-jg1Y", "UCq0OueAsdxH6b8nyAspwViw", 42, 72),  # Universal Pictures
    ("The Nightingale", "2027-03-19", "gNHr2-JjKRM", "UCz97F7dMxBNOfGYu3rx8aCw", 67, 97),  # Sony Pictures
    ("Day Drinker", "2027-03-26", "bhKKR5He_Fo", "UCJ6nMHaJPZvsJ-HmUmj1SeA", 53, 74),  # Lionsgate
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
    for film, release, vid, channel_id, start, end in CURATED:
        if release <= today:
            print(f"skip {film}: already released", file=sys.stderr)
            continue
        if not WINDOW[0] <= release <= WINDOW[1]:
            print(f"skip {film}: outside release window", file=sys.stderr)
            continue
        d = info(vid)
        if not d or not d.get("playable_in_embed") or (d.get("age_limit") or 0) or d.get("channel_id") != channel_id:
            print(f"skip {film}: not verified ({vid})", file=sys.stderr)
            continue
        # schema: { title, release_date, youtube_id, start, end } (start/end = muted header clip, seconds)
        if not (20 <= end - start <= 45 and end < int(d["duration"])):
            print(f"skip {film}: bad clip {start}-{end}", file=sys.stderr)
            continue
        out.append({"title": film, "release_date": release, "youtube_id": vid, "start": start, "end": end})
    out.sort(key=lambda t: (t["title"] != "Avengers: Doomsday", t["release_date"]))
    OUT.write_text(json.dumps({"generated": today, "items": out}, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(out)} trailers", file=sys.stderr)
    return 0 if out else 1


if __name__ == "__main__":
    raise SystemExit(main())
