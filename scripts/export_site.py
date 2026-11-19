"""Write the public static site used by GitHub Pages.

The export talks only to the local catalog. Set REVIEWS_LOCAL_ONLY so a
private database URL is never opened and visitor rows are not copied in.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

FORBIDDEN = (
    "postgresql://",
    "postgres://",
    "DATABASE_URL",
    "SECRET_KEY",
    "TMDB_API_KEY",
    "official_database",
)


def destination(out: Path, url_path: str) -> Path:
    path = url_path.split("?", 1)[0]
    if path in ("", "/"):
        return out / "index.html"
    name = path.strip("/")
    if "." in Path(name).name:
        return out / name
    return out / name / "index.html"


def catalog_path(kind: str, page: int, sort: str, genre_id: int | None = None) -> str:
    if kind == "browse":
        if sort != "rating" and page > 1:
            return f"/browse/sort/{sort}/page/{page}"
        if sort != "rating":
            return f"/browse/sort/{sort}"
        if page > 1:
            return f"/browse/page/{page}"
        return "/browse"
    if sort != "rating" and page > 1:
        return f"/genre/{genre_id}/sort/{sort}/page/{page}"
    if sort != "rating":
        return f"/genre/{genre_id}/sort/{sort}"
    if page > 1:
        return f"/genre/{genre_id}/page/{page}"
    return f"/genre/{genre_id}"


def collect_paths() -> list[str]:
    from data.year_movies import all_years
    from services import library, series, tmdb

    paths = [
        "/",
        "/about",
        "/reviews",
        "/upcoming",
        "/categories",
        "/search",
        "/movies",
        "/series",
        "/browse",
        "/robots.txt",
        "/sitemap.xml",
    ]
    for year in all_years():
        paths.append(f"/year/{year}")
        paths.append(f"/movies/year/{year}")
    for entry in series.series_year_index():
        paths.append(f"/series/year/{entry['year']}")

    sorts = [key for key, _ in library.SORT_OPTIONS]
    for sort in sorts:
        payload = library.browse_catalog(page=1, sort=sort)
        for page in range(1, payload["total_pages"] + 1):
            paths.append(catalog_path("browse", page, sort))

    for genre in tmdb.get_genres():
        genre_id = genre.get("id")
        if not genre_id:
            continue
        name = (genre.get("name") or "").strip().lower()
        if name in {"adult", "nc-17"}:
            continue
        for sort in sorts:
            payload = library.movies_by_genre(int(genre_id), page=1, sort=sort)
            total_pages = payload["total_pages"] if payload["total_results"] else 1
            for page in range(1, total_pages + 1):
                paths.append(catalog_path("genre", page, sort, int(genre_id)))

    for movie in library.all_trailer_movies():
        paths.append(f"/watch/{movie['id']}")
        paths.append(f"/movie/{movie['id']}")
    for show in series.all_series_entries():
        if show.get("id") and show.get("trailer_key"):
            paths.append(f"/series/watch/{show['id']}")

    return list(dict.fromkeys(paths))


def reset_dir(out: Path) -> None:
    resolved = out.resolve()
    if resolved == Path("/").resolve() or resolved == ROOT.resolve():
        raise SystemExit(f"refusing to clear {resolved}")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)


def export(out: Path) -> int:
    os.environ.setdefault("REVIEWS_LOCAL_ONLY", "1")
    os.environ.setdefault("STATIC_EXPORT", "1")
    empty = Path(tempfile.gettempdir()) / "2daymovie-export-reviews.db"
    os.environ["REVIEWS_SQLITE_PATH"] = str(empty)
    os.environ["DATABASE_URL"] = ""

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from app import app

    reset_dir(out)
    client = app.test_client()
    paths = collect_paths()
    failures: list[tuple[str, int]] = []
    for index, path in enumerate(paths, start=1):
        response = client.get(path)
        if response.status_code != 200:
            failures.append((path, response.status_code))
            continue
        dest = destination(out, path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.data)
        if index % 200 == 0:
            print(f"wrote {index}/{len(paths)}")

    missing = client.get("/this-page-is-not-in-the-catalog")
    (out / "404.html").write_bytes(missing.data)
    shutil.copytree(STATIC, out / "static", dirs_exist_ok=True)
    (out / ".nojekyll").write_text("", encoding="utf-8")

    leaked = []
    for file in out.rglob("*"):
        if not file.is_file() or file.suffix.lower() not in {".html", ".txt", ".xml", ".js", ".css", ".json"}:
            continue
        text = file.read_text(encoding="utf-8", errors="ignore")
        for needle in FORBIDDEN:
            if needle in text:
                leaked.append(f"{file.relative_to(out)} contains {needle}")
                break
    if failures or leaked:
        for path, status in failures:
            print(f"FAIL {status} {path}")
        for line in leaked:
            print(f"FAIL {line}")
        return 1
    print(f"exported {len(paths)} pages to {out}")
    return 0


def main() -> int:
    out = ROOT / "docs"
    args = sys.argv[1:]
    if "--out" in args:
        out = Path(args[args.index("--out") + 1])
        if not out.is_absolute():
            out = ROOT / out
    return export(out)


if __name__ == "__main__":
    raise SystemExit(main())
