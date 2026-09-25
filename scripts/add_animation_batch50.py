"""Add 50 missing animation / cartoon / series titles (2000–2027)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.add_missing_titles import (  # noqa: E402
    YEAR_OUT,
    SERIES_OUT,
    HEADERS,
    append_unique,
    enrich_movie,
    enrich_tv,
    search_movie,
    search_tv,
)
import requests

# Exactly 50 titles not already in the library (balanced across years).
BATCH: list[tuple[str, str, int]] = [
    ("movie", "The Emperor's New Groove", 2000),
    ("movie", "Brother Bear", 2003),
    ("movie", "Shark Tale", 2004),
    ("movie", "Madagascar", 2005),
    ("movie", "Cars", 2006),
    ("movie", "Over the Hedge", 2006),
    ("movie", "Bee Movie", 2007),
    ("movie", "Kung Fu Panda", 2008),
    ("movie", "Fantastic Mr. Fox", 2009),
    ("movie", "Tangled", 2010),
    ("movie", "Despicable Me", 2010),
    ("movie", "Rango", 2011),
    ("movie", "The Adventures of Tintin", 2011),
    ("movie", "Brave", 2012),
    ("movie", "Wreck-It Ralph", 2012),
    ("movie", "Frozen", 2013),
    ("movie", "The Croods", 2013),
    ("movie", "The LEGO Movie", 2014),
    ("movie", "Big Hero 6", 2014),
    ("movie", "The Good Dinosaur", 2015),
    ("movie", "Moana", 2016),
    ("movie", "The Boss Baby", 2017),
    ("movie", "Incredibles 2", 2018),
    ("movie", "Toy Story 4", 2019),
    ("movie", "Frozen II", 2019),
    ("movie", "Onward", 2020),
    ("movie", "Luca", 2021),
    ("movie", "Turning Red", 2022),
    ("movie", "The Bad Guys", 2022),
    ("movie", "Elemental", 2023),
    ("movie", "Spider-Man: Across the Spider-Verse", 2023),
    ("movie", "Inside Out 2", 2024),
    ("movie", "Moana 2", 2024),
    ("series", "Avatar: The Last Airbender", 2005),
    ("series", "Phineas and Ferb", 2007),
    ("series", "Adventure Time", 2010),
    ("series", "Regular Show", 2010),
    ("series", "The Amazing World of Gumball", 2011),
    ("series", "Gravity Falls", 2012),
    ("series", "Steven Universe", 2013),
    ("series", "Rick and Morty", 2013),
    ("series", "Star vs. the Forces of Evil", 2015),
    ("series", "We Bare Bears", 2015),
    ("series", "Bluey", 2018),
    ("series", "The Dragon Prince", 2018),
    ("series", "Amphibia", 2019),
    ("series", "The Owl House", 2020),
    ("series", "Arcane", 2021),
    ("series", "Invincible", 2021),
    ("series", "Hazbin Hotel", 2024),
]


def main() -> int:
    assert len(BATCH) == 50, len(BATCH)
    session = requests.Session()
    session.headers.update(HEADERS)
    movies = json.loads(YEAR_OUT.read_text(encoding="utf-8"))
    series = json.loads(SERIES_OUT.read_text(encoding="utf-8"))
    added_m = added_s = 0
    missed: list[str] = []

    for i, (kind, title, year) in enumerate(BATCH, 1):
        print(f"[{i}/50] {kind} {year} {title}", flush=True)
        try:
            if kind == "movie":
                mid = search_movie(session, title, year)
                time.sleep(0.22)
                if not mid:
                    missed.append(f"movie miss {title}")
                    continue
                row = enrich_movie(session, mid, title, year)
                time.sleep(0.18)
                if not row:
                    missed.append(f"movie no-trailer {title} id={mid}")
                    continue
                if append_unique(movies, row, "movie"):
                    added_m += 1
                    print(f"  + {row['title']} ({row['id']})", flush=True)
                else:
                    print("  skip dup", flush=True)
            else:
                tid = search_tv(session, title)
                time.sleep(0.22)
                if not tid:
                    missed.append(f"series miss {title}")
                    continue
                row = enrich_tv(session, tid, title, year)
                time.sleep(0.18)
                if not row:
                    missed.append(f"series no-trailer {title} id={tid}")
                    continue
                if append_unique(series, row, "series"):
                    added_s += 1
                    print(f"  + {row['title']} ({row['id']})", flush=True)
                else:
                    print("  skip dup", flush=True)
        except Exception as exc:
            missed.append(f"error {title}: {exc}")
            print(f"  ERR {exc}", flush=True)

    YEAR_OUT.write_text(json.dumps(movies, ensure_ascii=False, indent=2), encoding="utf-8")
    SERIES_OUT.write_text(json.dumps(series, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"DONE movies+={added_m} series+={added_s} totals={len(movies)}/{len(series)}")
    if missed:
        print("MISSED:")
        for line in missed:
            print(" ", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
