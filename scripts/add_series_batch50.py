"""Add 50 new TV series spanning every year from 2000 to 2027."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.add_missing_titles import (  # noqa: E402
    SERIES_OUT,
    HEADERS,
    append_unique,
    enrich_tv,
    search_tv,
)
import requests

# Exactly 50 series; every year 2000–2027 appears at least once.
BATCH: list[tuple[str, int]] = [
    ("Malcolm in the Middle", 2000),
    ("Gilmore Girls", 2000),
    ("Band of Brothers", 2001),
    ("Scrubs", 2001),
    ("Firefly", 2002),
    ("Kim Possible", 2002),
    ("Nip/Tuck", 2003),
    ("Arrested Development", 2003),
    ("Desperate Housewives", 2004),
    ("House", 2004),
    ("Prison Break", 2005),
    ("How I Met Your Mother", 2005),
    ("Dexter", 2006),
    ("Heroes", 2006),
    ("Mad Men", 2007),
    ("Chuck", 2007),
    ("Breaking Bad", 2008),
    ("Fringe", 2008),
    ("Modern Family", 2009),
    ("Community", 2009),
    ("The Walking Dead", 2010),
    ("Downton Abbey", 2010),
    ("Game of Thrones", 2011),
    ("American Horror Story", 2011),
    ("Girls", 2012),
    ("Arrow", 2012),
    ("Orange Is the New Black", 2013),
    ("Brooklyn Nine-Nine", 2013),
    ("Fargo", 2014),
    ("True Detective", 2014),
    ("Better Call Saul", 2015),
    ("Mr. Robot", 2015),
    ("Stranger Things", 2016),
    ("Westworld", 2016),
    ("The Handmaid's Tale", 2017),
    ("Mindhunter", 2017),
    ("Succession", 2018),
    ("The Boys", 2019),
    ("Euphoria", 2019),
    ("Ted Lasso", 2020),
    ("The Queen's Gambit", 2020),
    ("WandaVision", 2021),
    ("Only Murders in the Building", 2021),
    ("House of the Dragon", 2022),
    ("The Bear", 2022),
    ("The Last of Us", 2023),
    ("Ripley", 2024),
    ("Alien: Earth", 2025),
    ("Blade Runner 2099", 2026),
    ("Crystal Lake", 2027),
]


def main() -> int:
    assert len(BATCH) == 50, len(BATCH)
    covered = {y for _, y in BATCH}
    missing_years = [y for y in range(2000, 2028) if y not in covered]
    print("years covered", len(covered), "missing", missing_years, flush=True)

    session = requests.Session()
    session.headers.update(HEADERS)
    series = json.loads(SERIES_OUT.read_text(encoding="utf-8"))
    added = 0
    missed: list[str] = []

    for i, (title, year) in enumerate(BATCH, 1):
        print(f"[{i}/50] {year} {title}", flush=True)
        try:
            tid = search_tv(session, title)
            time.sleep(0.2)
            if not tid:
                missed.append(f"miss {title}")
                continue
            row = enrich_tv(session, tid, title, year)
            time.sleep(0.15)
            if not row:
                missed.append(f"no-trailer {title} id={tid}")
                continue
            if append_unique(series, row, "series"):
                added += 1
                print(f"  + {row['title']} ({row['id']})", flush=True)
            else:
                print("  skip dup", flush=True)
        except Exception as exc:
            missed.append(f"error {title}: {exc}")
            print(f"  ERR {exc}", flush=True)

    SERIES_OUT.write_text(json.dumps(series, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"DONE series+={added} total={len(series)}")
    if missed:
        print("MISSED:")
        for line in missed:
            print(" ", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
