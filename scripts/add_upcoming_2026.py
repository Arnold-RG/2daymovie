"""Merge Oct–Dec 2026 movies and Fall 2026 series into catalogs."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.year_movies import YEAR_MOVIES  # noqa: E402
from data import series_shows as series_mod  # noqa: E402

NEW_2026_MOVIES = [
    # October
    "Digger",
    "Clayface",
    "Street Fighter",
    "Wildwood",
    "Whalefall",
    "Klara and the Sun",
    "Hope",
    "The Beast",
    "Other Mommy",
    # November
    "The Hunger Games: Sunrise on the Reaping",
    "Ramayana: Part 1",
    "A Christmas Carol",
    "Wicker",
    "The Cat in the Hat",
    "Hexe",
    # December
    "Avengers: Doomsday",
    "Dune: Part Three",
    "Violent Night 2",
    "Ray Gunn",
    "Jumanji: Open World",
    # Already released / notable 2026
    "Coyote vs. Acme",
    "The Super Mario Galaxy Movie",
]

# Already in catalog (skip): Project Hail Mary, 28 Years Later..., Obsession, Michael,
# The Drama, The Furious, Backrooms, Zootopia 2, Tron: Ares, Predator: Badlands,
# Now You See Me..., Mortal Kombat II

NEW_SERIES = [
    {"title": "Blade Runner 2099", "start": 2026, "end": None},
    {"title": "Carrie", "start": 2026, "end": None},
    {"title": "VisionQuest", "start": 2026, "end": None},
    {"title": "Tip Toe", "start": 2026, "end": None},
    {"title": "Crystal Lake", "start": 2026, "end": None},
    {"title": "A Knight of the Seven Kingdoms", "start": 2026, "end": None},
    {"title": "Pride & Prejudice", "start": 2026, "end": None},
    {"title": "Lupin", "start": 2021, "end": None},
    {"title": "Wonder Man", "start": 2026, "end": None},
    {"title": "Widow's Bay", "start": 2026, "end": None},
    {"title": "Black Doves", "start": 2024, "end": None},
    {"title": "The Lowdown", "start": 2025, "end": None},
    {"title": "Lanterns", "start": 2026, "end": None},
    {"title": "Dark Matter", "start": 2024, "end": None},
    {"title": "Silo", "start": 2023, "end": None},
]


def norm(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def rewrite_year_movies(merged: dict) -> None:
    lines = [
        '"""Curated 2daymovie library: notable films 2000–2026 (by release year)."""',
        "",
        "YEAR_MOVIES = {",
    ]
    for year in sorted(merged):
        lines.append(f"    {year}: [")
        for title in merged[year]:
            lines.append(f"        {title!r},")
        lines.append("    ],")
    lines.extend(
        [
            "}",
            "",
            "",
            "def all_years():",
            "    return sorted(YEAR_MOVIES.keys(), reverse=True)",
            "",
            "",
            "def titles_for_year(year: int):",
            "    return YEAR_MOVIES.get(year, [])",
            "",
            "",
            "def total_titles():",
            "    return sum(len(v) for v in YEAR_MOVIES.values())",
            "",
        ]
    )
    (ROOT / "data" / "year_movies.py").write_text("\n".join(lines) + "\n", encoding="utf-8")


def rewrite_series(shows: list[dict]) -> None:
    lines = [
        '"""Curated prestige / influential TV series spanning 2000–2026."""',
        "",
        "from __future__ import annotations",
        "",
        "# title, start_year, end_year (None = ongoing / present)",
        "SERIES_SHOWS: list[dict] = [",
    ]
    for show in shows:
        end = "None" if show["end"] is None else str(show["end"])
        lines.append(
            f'    {{"title": {show["title"]!r}, "start": {show["start"]}, "end": {end}}},'
        )
    lines.extend(
        [
            "]",
            "",
            "",
            "def all_series() -> list[dict]:",
            "    return list(SERIES_SHOWS)",
            "",
            "",
            "def total_series() -> int:",
            "    return len(SERIES_SHOWS)",
            "",
            "",
            "def years_span_label(show: dict) -> str:",
            "    start = show.get(\"start\")",
            "    end = show.get(\"end\")",
            "    if end is None:",
            '        return f"{start}–present"',
            "    if start == end:",
            "        return str(start)",
            '    return f"{start}–{end}"',
            "",
        ]
    )
    (ROOT / "data" / "series_shows.py").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    merged = {y: list(v) for y, v in YEAR_MOVIES.items()}
    seen = {norm(t) for t in merged[2026]}
    added_m = 0
    for title in NEW_2026_MOVIES:
        key = norm(title)
        if key in seen:
            continue
        # soft-dedupe near matches already present
        if any(key in norm(t) or norm(t) in key for t in merged[2026]):
            # still add if not exact; skip only exact
            pass
        seen.add(key)
        merged[2026].append(title)
        added_m += 1

    # Force-exact dedupe pass
    final_2026 = []
    seen2: set[str] = set()
    for t in merged[2026]:
        k = norm(t)
        if k in seen2:
            continue
        seen2.add(k)
        final_2026.append(t)
    merged[2026] = final_2026
    rewrite_year_movies(merged)
    print(f"2026 movies: +{added_m} unique adds -> {len(merged[2026])} total")

    shows = list(series_mod.SERIES_SHOWS)
    existing = {norm(s["title"]) for s in shows}
    added_s = 0
    for show in NEW_SERIES:
        k = norm(show["title"])
        if k in existing:
            # keep Yellowjackets / Slow Horses as already listed
            continue
        shows.append(show)
        existing.add(k)
        added_s += 1
    # stable-ish order by start year then title
    shows.sort(key=lambda s: (s["start"], s["title"]))
    rewrite_series(shows)
    print(f"series: +{added_s} -> {len(shows)} total")


if __name__ == "__main__":
    main()
