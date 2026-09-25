"""Add another 50 missing animation / cartoon titles."""

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

BATCH: list[tuple[str, str, int]] = [
    ("movie", "Dinosaur", 2000),
    ("movie", "The Road to El Dorado", 2000),
    ("movie", "Atlantis: The Lost Empire", 2001),
    ("movie", "Jimmy Neutron: Boy Genius", 2001),
    ("movie", "Treasure Planet", 2002),
    ("movie", "Spirit: Stallion of the Cimarron", 2002),
    ("movie", "Sinbad: Legend of the Seven Seas", 2003),
    ("movie", "Home on the Range", 2004),
    ("movie", "The Polar Express", 2004),
    ("movie", "Robots", 2005),
    ("movie", "Chicken Little", 2005),
    ("movie", "Flushed Away", 2006),
    ("movie", "Happy Feet", 2006),
    ("movie", "Meet the Robinsons", 2007),
    ("movie", "Surf's Up", 2007),
    ("movie", "Horton Hears a Who!", 2008),
    ("movie", "Bolt", 2008),
    ("movie", "Monsters vs Aliens", 2009),
    ("movie", "Cloudy with a Chance of Meatballs", 2009),
    ("movie", "Megamind", 2010),
    ("movie", "Rio", 2011),
    ("movie", "Puss in Boots", 2011),
    ("movie", "Hotel Transylvania", 2012),
    ("movie", "Rise of the Guardians", 2012),
    ("movie", "The Book of Life", 2014),
    ("movie", "Penguins of Madagascar", 2014),
    ("movie", "Kubo and the Two Strings", 2016),
    ("movie", "Trolls", 2016),
    ("movie", "Isle of Dogs", 2018),
    ("movie", "Ralph Breaks the Internet", 2018),
    ("movie", "Abominable", 2019),
    ("movie", "The Mitchells vs. the Machines", 2021),
    ("movie", "Puss in Boots: The Last Wish", 2022),
    ("movie", "Migration", 2023),
    ("movie", "Wish", 2023),
    ("movie", "The Garfield Movie", 2024),
    ("movie", "Ultraman: Rising", 2024),
    ("series", "SpongeBob SquarePants", 1999),
    ("series", "Samurai Jack", 2001),
    ("series", "Teen Titans", 2003),
    ("series", "Foster's Home for Imaginary Friends", 2004),
    ("series", "Ben 10", 2005),
    ("series", "Avatar: The Legend of Korra", 2012),
    ("series", "Teen Titans Go!", 2013),
    ("series", "Over the Garden Wall", 2014),
    ("series", "BoJack Horseman", 2014),
    ("series", "Castlevania", 2017),
    ("series", "Harley Quinn", 2019),
    ("series", "Cyberpunk: Edgerunners", 2022),
    ("series", "Delicious in Dungeon", 2024),
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
                time.sleep(0.2)
                if not mid:
                    missed.append(f"movie miss {title}")
                    continue
                row = enrich_movie(session, mid, title, year)
                time.sleep(0.15)
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
                time.sleep(0.2)
                if not tid:
                    missed.append(f"series miss {title}")
                    continue
                row = enrich_tv(session, tid, title, year)
                time.sleep(0.15)
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
