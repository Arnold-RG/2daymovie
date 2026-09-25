"""Keep only catalog rows that have a valid on-site trailer embed key."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YT = re.compile(r"^[A-Za-z0-9_-]{11}$")


def valid_key(key: str | None) -> bool:
    if not key or not YT.fullmatch(key):
        return False
    if key.startswith("mobile") or key.endswith("-") or "web-" in key:
        return False
    return True


def prune(path: Path) -> tuple[int, int]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    before = len(rows)
    kept = [r for r in rows if r.get("id") and valid_key(r.get("trailer_key"))]
    path.write_text(json.dumps(kept, ensure_ascii=False, indent=2), encoding="utf-8")
    return before, len(kept)


def rewrite_year_movies_from_catalog() -> None:
    catalog = json.loads((ROOT / "data" / "year_catalog.json").read_text(encoding="utf-8"))
    by_year: dict[int, list[str]] = {}
    for row in catalog:
        year = row.get("year")
        title = row.get("query") or row.get("title")
        if not year or not title:
            continue
        by_year.setdefault(int(year), []).append(title)
    lines = [
        '"""Curated 2daymovie library: trailer-ready films 2000–2026."""',
        "",
        "YEAR_MOVIES = {",
    ]
    for year in sorted(by_year):
        lines.append(f"    {year}: [")
        # preserve order, unique
        seen = set()
        for title in by_year[year]:
            if title in seen:
                continue
            seen.add(title)
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


def rewrite_series_from_catalog() -> None:
    catalog = json.loads((ROOT / "data" / "series_catalog.json").read_text(encoding="utf-8"))
    lines = [
        '"""Curated TV series with on-site official trailer embeds."""',
        "",
        "from __future__ import annotations",
        "",
        "SERIES_SHOWS: list[dict] = [",
    ]
    for row in sorted(catalog, key=lambda r: (r.get("start") or 0, r.get("query") or "")):
        title = row.get("query") or row.get("title")
        start = row.get("start")
        end = row.get("end")
        end_lit = "None" if end is None else str(end)
        if not title or not start:
            continue
        lines.append(
            f'    {{"title": {title!r}, "start": {int(start)}, "end": {end_lit}}},'
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
    for name in ("year_catalog.json", "series_catalog.json"):
        before, after = prune(ROOT / "data" / name)
        print(f"{name}: {before} -> {after}")
    rewrite_year_movies_from_catalog()
    rewrite_series_from_catalog()
    print("rewrote year_movies.py and series_shows.py")


if __name__ == "__main__":
    main()
