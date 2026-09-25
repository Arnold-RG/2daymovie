"""Add only missing curated titles into catalogs + upcoming lists."""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

YEAR_OUT = ROOT / "data" / "year_catalog.json"
SERIES_OUT = ROOT / "data" / "series_catalog.json"
UPCOMING_PY = ROOT / "data" / "upcoming.py"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
YT_RE = re.compile(r"(?:youtube\.com/embed/|youtu\.be/)([A-Za-z0-9_-]{11})")
DATA_ID_RE = re.compile(r'data-id="([A-Za-z0-9_-]{11})"')
GENRE_RE = re.compile(r'href="/genre/(\d+)-[^"]+/movie"')
PLAYABLE_RE = re.compile(r'"playableInEmbed"\s*:\s*(true|false)')
YT_KEY = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Only titles confirmed missing from catalogs (plus Batman Part II false-match fix).
MISSING = [
    ("movie", "The Angry Birds Movie 3", 2026),
    ("movie", "Ebenezer", 2026),
    ("movie", "Sonic the Hedgehog 4", 2027),
    ("movie", "Avengers: Secret Wars", 2027),
    ("movie", "The Batman Part II", 2027),
    ("movie", "Spider-Man: Beyond the Spider-Verse", 2027),
    ("movie", "Shrek 5", 2027),
    ("movie", "Toy Story 5", 2026),
    ("movie", "Ice Age: Boiling Point", 2026),
    ("movie", "TRON: Ares", 2025),
    ("movie", "Avatar: Fire and Ash", 2025),
    ("movie", "The Devil Wears Prada 2", 2026),
    ("movie", "The Dog Stars", 2026),
    ("movie", "Send Help", 2026),
    ("movie", "Psycho Killer", 2026),
    ("movie", "The Testament of Ann Lee", 2026),
    ("movie", "Ready or Not 2: Here I Come", 2026),
    ("movie", "Star Wars: The Mandalorian and Grogu", 2026),
    ("series", "Black Clover", 2026),  # Season 2 search seed
    ("series", "The Apothecary Diaries", 2026),
    ("series", "Firefly Wedding", 2026),
    ("series", "Akane-banashi", 2027),
    ("series", "The Rising of the Shield Hero", 2027),
    ("series", "Glasses with a Chance of Delinquent", 2027),
    ("series", "Witch and Mercenary", 2027),
    ("series", "ONE PIECE", 2027),  # live-action / THE ONE PIECE remake search
    ("series", "Ahsoka", 2027),
    ("series", "Star Wars: Maul – Shadow Lord", 2026),
    ("series", "X-Men '97", 2026),
    ("series", "Daredevil: Born Again", 2026),
    ("series", "The Punisher", 2026),
    ("series", "Wonder Man", 2026),
    ("series", "Marvel Zombies", 2025),
    ("series", "Eyes of Wakanda", 2025),
    ("series", "Sakamoto Days", 2027),
    ("series", "Mashle", 2027),
    ("series", "Jujutsu Kaisen", 2027),
    ("series", "Dandadan", 2027),
    ("series", "One Piece", 2026),  # Elbaph arc / ongoing
    ("series", "Shangri-La Frontier", 2027),
    ("series", "Undead Unluck", 2027),
    ("series", "Witch Watch", 2027),
    ("series", "Blue Box", 2026),
    ("series", "VisionQuest", 2026),
]

# Display labels for upcoming shelves (keep user's naming where useful).
UPCOMING_LABELS = {
    ("movie", 2025): [
        "TRON: Ares",
        "Avatar: Fire and Ash",
    ],
    ("movie", 2026): [
        "The Angry Birds Movie 3",
        "Ebenezer",
        "Toy Story 5",
        "Ice Age: Boiling Point",
        "The Devil Wears Prada 2",
        "The Dog Stars",
        "Send Help",
        "Psycho Killer",
        "The Testament of Ann Lee",
        "Ready or Not 2: Here I Come",
        "Star Wars: The Mandalorian and Grogu",
    ],
    ("movie", 2027): [
        "Sonic the Hedgehog 4",
        "Avengers: Secret Wars",
        "The Batman Part II",
        "Spider-Man: Beyond the Spider-Verse",
        "Shrek 5",
    ],
    ("series", 2025): [
        "Marvel Zombies",
        "Eyes of Wakanda",
    ],
    ("series", 2026): [
        "Black Clover Season 2",
        "The Apothecary Diaries Season 3",
        "Firefly Wedding",
        "Star Wars: Maul – Shadow Lord",
        "X-Men '97 Season 2",
        "Daredevil: Born Again Season 2",
        "The Punisher: One Last Kill",
        "Wonder Man",
        "One Piece: Elbaph Arc",
        "Blue Box Season 2",
        "VisionQuest",
    ],
    ("series", 2027): [
        "Akane-banashi Season 2",
        "The Rising of the Shield Hero Season 5",
        "Glasses with a Chance of Delinquent",
        "Witch and Mercenary",
        "THE ONE PIECE",
        "Star Wars: Ahsoka Season 2",
        "SAKAMOTO DAYS Season 2",
        "Mashle Season 3",
        "Jujutsu Kaisen Season 4",
        "Dandadan Season 3",
        "Shangri-La Frontier Season 3",
        "Undead Unluck Season 2",
        "Witch Watch Season 2",
    ],
}

# Prefer these TMDB search queries when the display title is awkward.
SEARCH_ALIASES = {
    "THE ONE PIECE": ["ONE PIECE", "One Piece Remake"],
    "Star Wars: Maul – Shadow Lord": ["Maul Shadow Lord", "Star Wars Maul"],
    "The Punisher": ["Punisher One Last Kill", "The Punisher"],
    "ONE PIECE": ["ONE PIECE"],
    "One Piece": ["One Piece"],
    "X-Men '97": ["X-Men '97", "X-Men 97"],
}


def _norm(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (title or "").lower())


def _valid_key(key: str | None) -> bool:
    if not key or not YT_KEY.fullmatch(key):
        return False
    if key.startswith("mobile") or "web-" in key or key.endswith("-"):
        return False
    return True


def _pick_keys(page_html: str) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for key in DATA_ID_RE.findall(page_html) + YT_RE.findall(page_html):
        if not _valid_key(key) or key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys[:12]


def is_embeddable(key: str, session: requests.Session) -> bool:
    try:
        oe = session.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={key}", "format": "json"},
            timeout=18,
        )
        if oe.status_code != 200:
            return False
        watch = session.get(f"https://www.youtube.com/watch?v={key}", timeout=20)
        text = watch.text or ""
        match = PLAYABLE_RE.search(text)
        if match and match.group(1) == "false":
            return False
        if "playback on other websites has been disabled" in text.lower():
            return False
        return True
    except Exception:
        return False


def search_movie(session: requests.Session, title: str, year: int) -> int | None:
    queries = SEARCH_ALIASES.get(title, [title])
    for q in queries:
        url = f"https://www.themoviedb.org/search/movie?query={quote_plus(q)}"
        r = session.get(url, timeout=25)
        if r.status_code != 200:
            continue
        html = r.text
        candidates = []
        for m in re.finditer(r'/movie/(\d+)[^"\']*["\'].{0,500}?(\d{4})', html, re.S):
            mid = int(m.group(1))
            y = int(m.group(2))
            if 1900 <= y <= 2035:
                candidates.append((abs(y - year), y, mid))
        if candidates:
            best: dict[int, tuple[int, int, int]] = {}
            for item in candidates:
                mid = item[2]
                if mid not in best or item < best[mid]:
                    best[mid] = item
            return sorted(best.values())[0][2]
        m = re.search(r"/movie/(\d+)", html)
        if m:
            return int(m.group(1))
    return None


def search_tv(session: requests.Session, title: str) -> int | None:
    queries = SEARCH_ALIASES.get(title, [title])
    for q in queries:
        url = f"https://www.themoviedb.org/search/tv?query={quote_plus(q)}"
        r = session.get(url, timeout=25)
        if r.status_code != 200:
            continue
        m = re.search(r"/tv/(\d+)", r.text)
        if m:
            return int(m.group(1))
    return None


def enrich_movie(session: requests.Session, movie_id: int, query: str, year: int) -> dict | None:
    url = f"https://www.themoviedb.org/movie/{movie_id}"
    r = session.get(url, timeout=25)
    if r.status_code != 200:
        return None
    html = r.text
    ogs = re.findall(r'property="og:image" content="([^"]+)"', html)
    poster = backdrop = None
    for u in ogs:
        m = re.search(r"/t/p/w\d+(/[A-Za-z0-9_]+\.jpg)", u)
        if not m:
            continue
        path = m.group(1)
        if "/w500/" in u or "/w342/" in u:
            poster = path
        if "/w780/" in u or "/w1280/" in u:
            backdrop = path
    title_m = re.search(r"<title>(.*?)\s*\(", html)
    title = (
        title_m.group(1).strip().replace("&#39;", "'").replace("&amp;", "&")
        if title_m
        else query
    )
    ov_m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
    overview = (ov_m.group(1) if ov_m else "").replace("&#39;", "'").replace("&amp;", "&")
    keys = _pick_keys(html)
    if not keys:
        vr = session.get(f"{url}/videos", timeout=25)
        if vr.status_code == 200:
            keys = _pick_keys(vr.text)
    good = [k for k in keys if is_embeddable(k, session)]
    if not good:
        return None
    genres: list[int] = []
    seen: set[int] = set()
    for m in GENRE_RE.finditer(html):
        gid = int(m.group(1))
        if gid not in seen:
            seen.add(gid)
            genres.append(gid)
    return {
        "id": movie_id,
        "year": year,
        "query": query,
        "title": title,
        "overview": overview[:700],
        "vote_average": 0,
        "poster_path": poster,
        "backdrop_path": backdrop or poster,
        "release_date": f"{year}-01-01",
        "genre_ids": genres,
        "trailer_key": good[0],
        "trailer_keys": good,
        "watch_link": None,
    }


def enrich_tv(session: requests.Session, tv_id: int, query: str, year: int) -> dict | None:
    url = f"https://www.themoviedb.org/tv/{tv_id}"
    r = session.get(url, timeout=25)
    if r.status_code != 200:
        return None
    html = r.text
    ogs = re.findall(r'property="og:image" content="([^"]+)"', html)
    poster = backdrop = None
    for u in ogs:
        m = re.search(r"/t/p/w\d+(/[A-Za-z0-9_]+\.jpg)", u)
        if not m:
            continue
        path = m.group(1)
        if "/w500/" in u or "/w342/" in u:
            poster = path
        if "/w780/" in u or "/w1280/" in u:
            backdrop = path
    title_m = re.search(r"<title>(.*?)\s*\(", html)
    title = (
        title_m.group(1).strip().replace("&#39;", "'").replace("&amp;", "&")
        if title_m
        else query
    )
    ov_m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html)
    overview = (ov_m.group(1) if ov_m else "").replace("&#39;", "'").replace("&amp;", "&")
    keys = _pick_keys(html)
    if not keys:
        vr = session.get(f"{url}/videos", timeout=25)
        if vr.status_code == 200:
            keys = _pick_keys(vr.text)
    good = [k for k in keys if is_embeddable(k, session)]
    if not good:
        return None
    return {
        "id": tv_id,
        "query": query,
        "title": title,
        "overview": overview[:700],
        "poster_path": poster,
        "backdrop_path": backdrop or poster,
        "start": year,
        "end": None,
        "trailer_key": good[0],
        "trailer_keys": good,
        "watch_link": None,
    }


def append_unique(rows: list[dict], row: dict, kind: str) -> bool:
    rid = row.get("id")
    if not rid:
        return False
    for existing in rows:
        if existing.get("id") == rid:
            return False
        if kind == "movie" and _norm(existing.get("title")) == _norm(row.get("title")) and int(
            existing.get("year") or 0
        ) == int(row.get("year") or 0):
            return False
        if kind == "series" and _norm(existing.get("title")) == _norm(row.get("title")):
            return False
    rows.append(row)
    return True


def update_upcoming() -> None:
    text = UPCOMING_PY.read_text(encoding="utf-8")

    def merge(const_name: str, additions: list[str]) -> None:
        nonlocal text
        m = re.search(rf"{const_name}\s*=\s*(\[[^\]]*\])", text, re.S)
        if not m:
            print(f"WARN missing {const_name}")
            return
        current = eval(m.group(1), {"__builtins__": {}})  # trusted local file
        seen = {_norm(x) for x in current}
        merged = list(current)
        for title in additions:
            if _norm(title) in seen:
                continue
            merged.append(title)
            seen.add(_norm(title))
        rendered = json.dumps(merged, ensure_ascii=False)
        # prefer single-quoted python style like existing file
        rendered = "[" + ", ".join(
            "'" + t.replace("'", "\\'") + "'" for t in merged
        ) + "]"
        text = text[: m.start(1)] + rendered + text[m.end(1) :]

    merge("UPCOMING_MOVIES_2026", UPCOMING_LABELS[("movie", 2026)])
    # 2027 movies: Secret Wars may already be there
    merge("UPCOMING_MOVIES_2027", UPCOMING_LABELS[("movie", 2027)])
    # No 2025 const yet — inject if needed
    if "UPCOMING_MOVIES_2025" not in text:
        block = (
            "UPCOMING_MOVIES_2025 = ["
            + ", ".join("'" + t.replace("'", "\\'") + "'" for t in UPCOMING_LABELS[("movie", 2025)])
            + "]\n\n"
        )
        text = text.replace(
            '"""Upcoming 2026–2027 movies and series (titles only; linked via catalogs)."""\n\n',
            '"""Upcoming 2025–2027 movies and series (titles only; linked via catalogs)."""\n\n'
            + block,
        )
    else:
        merge("UPCOMING_MOVIES_2025", UPCOMING_LABELS[("movie", 2025)])

    series_add = UPCOMING_LABELS[("series", 2025)] + UPCOMING_LABELS[("series", 2026)] + UPCOMING_LABELS[("series", 2027)]
    merge("UPCOMING_SERIES", series_add)
    UPCOMING_PY.write_text(text, encoding="utf-8")
    print("updated upcoming.py")


def patch_upcoming_service() -> None:
    path = ROOT / "services" / "upcoming.py"
    text = path.read_text(encoding="utf-8")
    if "UPCOMING_MOVIES_2025" in text:
        return
    text = text.replace(
        "from data.upcoming import UPCOMING_MOVIES_2026, UPCOMING_MOVIES_2027, UPCOMING_SERIES",
        "from data.upcoming import (\n"
        "    UPCOMING_MOVIES_2025,\n"
        "    UPCOMING_MOVIES_2026,\n"
        "    UPCOMING_MOVIES_2027,\n"
        "    UPCOMING_SERIES,\n"
        ")",
    )
    # Insert 2025 helper before 2026 if missing
    if "def upcoming_movies_2025" not in text:
        helper = '''
def upcoming_movies_2025() -> list[dict[str, Any]]:
    return _movie_cards(
        UPCOMING_MOVIES_2025,
        2025,
        "Coming 2025. Trailer will appear here when available.",
    )

'''
        text = text.replace("def upcoming_movies_2026()", helper + "def upcoming_movies_2026()")
    if '"movies_2025"' not in text and "movies_2025" not in text:
        text = text.replace(
            'return {\n        "movies": upcoming_movies_2026(),\n        "movies_2027": upcoming_movies_2027(),\n        "series": upcoming_series(),\n    }',
            'return {\n        "movies_2025": upcoming_movies_2025(),\n        "movies": upcoming_movies_2026(),\n        "movies_2027": upcoming_movies_2027(),\n        "series": upcoming_series(),\n    }',
        )
    path.write_text(text, encoding="utf-8")
    print("patched services/upcoming.py")


def main() -> int:
    session = requests.Session()
    session.headers.update(HEADERS)

    movies = json.loads(YEAR_OUT.read_text(encoding="utf-8"))
    series = json.loads(SERIES_OUT.read_text(encoding="utf-8"))
    added_m = added_s = 0
    missed: list[str] = []

    for i, (kind, title, year) in enumerate(MISSING, 1):
        print(f"[{i}/{len(MISSING)}] {kind} {year} {title}", flush=True)
        try:
            if kind == "movie":
                mid = search_movie(session, title, year)
                time.sleep(0.25)
                if not mid:
                    missed.append(f"movie miss {title}")
                    continue
                row = enrich_movie(session, mid, title, year)
                time.sleep(0.2)
                if not row:
                    missed.append(f"movie no-embed-trailer {title} id={mid}")
                    continue
                if append_unique(movies, row, "movie"):
                    added_m += 1
                    print(f"  + movie {row['title']} ({row['id']}) trailers={len(row['trailer_keys'])}", flush=True)
                else:
                    print(f"  skip duplicate {row['title']}", flush=True)
            else:
                tid = search_tv(session, title)
                time.sleep(0.25)
                if not tid:
                    missed.append(f"series miss {title}")
                    continue
                row = enrich_tv(session, tid, title, year)
                time.sleep(0.2)
                if not row:
                    missed.append(f"series no-embed-trailer {title} id={tid}")
                    continue
                if append_unique(series, row, "series"):
                    added_s += 1
                    print(f"  + series {row['title']} ({row['id']}) trailers={len(row['trailer_keys'])}", flush=True)
                else:
                    print(f"  skip duplicate {row['title']}", flush=True)
        except Exception as exc:
            missed.append(f"error {title}: {exc}")
            print(f"  ERR {exc}", flush=True)

    YEAR_OUT.write_text(json.dumps(movies, ensure_ascii=False, indent=2), encoding="utf-8")
    SERIES_OUT.write_text(json.dumps(series, ensure_ascii=False, indent=2), encoding="utf-8")
    update_upcoming()
    patch_upcoming_service()
    print(f"DONE added movies={added_m} series={added_s} catalog_movies={len(movies)} catalog_series={len(series)}")
    if missed:
        print("MISSED:")
        for line in missed:
            print(" ", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
