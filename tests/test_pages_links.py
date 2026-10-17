"""Pages export keeps internal links under the repository subpath."""

from pathlib import Path

from scripts.check_internal_links import check_site, html_refs
from scripts.export_site import collect_paths


def test_collect_paths_includes_upcoming_watch_targets():
    from services import upcoming

    paths = set(collect_paths())
    assert "/year" in paths
    payload = upcoming.upcoming_payload()
    movies = []
    for bucket in ("movies_2025", "movies", "movies_2027"):
        movies.extend(payload[bucket])
    linked_movies = [movie for movie in movies if movie.get("status") == "trailer" and movie.get("id")]
    linked_series = [
        show for show in payload["series"] if show.get("status") == "trailer" and show.get("id")
    ]
    assert linked_movies
    assert linked_series
    for movie in linked_movies:
        assert f"/watch/{movie['id']}" in paths
        assert f"/movie/{movie['id']}" in paths
    for show in linked_series:
        assert f"/series/watch/{show['id']}" in paths


def test_upcoming_series_outside_the_shelf_still_render():
    from app import app
    from services import series, upcoming

    shelf = {show.get("id") for show in series.all_series_entries()}
    client = app.test_client()
    outside = []
    for show in upcoming.upcoming_payload()["series"]:
        if show.get("status") != "trailer" or not show.get("id"):
            continue
        response = client.get(f"/series/watch/{show['id']}")
        assert response.status_code == 200
        if show["id"] not in shelf:
            outside.append(show["id"])
    assert outside, "upcoming should link series that all_series_entries() omits"


def test_home_hero_links_include_pages_base(monkeypatch):
    monkeypatch.setenv("BASE_PATH", "/2daymovie")
    monkeypatch.setenv("REVIEWS_LOCAL_ONLY", "1")
    monkeypatch.setenv("DATABASE_URL", "")
    from app import create_app

    client = create_app().test_client()
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-href="/2daymovie/watch/' in html
    assert 'data-href="/watch/' not in html
    assert 'class="hero-now-title"' in html
    assert 'href="/watch/' not in html


def test_year_index_is_exported_page():
    from app import app

    client = app.test_client()
    page = client.get("/year")
    assert page.status_code == 200
    assert b"Movies by year" in page.data
    assert b"/year/2010" in page.data
    jump = client.get("/year?year=2010")
    assert jump.status_code in (301, 302, 308)
    assert jump.headers.get("Location", "").endswith("/year/2010")


def test_link_parser_reads_hero_and_search_index():
    html = """
    <div data-href="/2daymovie/watch/1"></div>
    <a href="/2daymovie/upcoming">Upcoming</a>
    <script type="application/json" id="search-index">[{"title": "A", "href": "/2daymovie/watch/2"}]</script>
    """
    urls = {url for _, url in html_refs(html)}
    assert "/2daymovie/watch/1" in urls
    assert "/2daymovie/upcoming" in urls
    assert "/2daymovie/watch/2" in urls


def test_checker_flags_root_relative_and_missing_pages(tmp_path: Path):
    (tmp_path / "index.html").write_text(
        """
        <link rel="stylesheet" href="/2daymovie/static/css/style.css" />
        <a href="/2daymovie/upcoming">Upcoming</a>
        <div data-href="/watch/621304"></div>
        <a class="hero-now-title" href="/watch/621304">Title</a>
        """,
        encoding="utf-8",
    )
    upcoming = tmp_path / "upcoming"
    upcoming.mkdir()
    (upcoming / "index.html").write_text(
        '<a href="/2daymovie/series/watch/138505">Marvel Zombies</a>',
        encoding="utf-8",
    )
    static_css = tmp_path / "static" / "css"
    static_css.mkdir(parents=True)
    (static_css / "style.css").write_text("", encoding="utf-8")

    errors = check_site(tmp_path, "/2daymovie")
    blob = "\n".join(errors)
    assert "/watch/621304" in blob
    assert "outside the Pages base" in blob
    assert "/2daymovie/series/watch/138505" in blob
    assert "does not match a file" in blob


def test_checker_ignores_svg_filter_refs_inside_data_uris(tmp_path: Path):
    (tmp_path / "index.html").write_text("<p>ok</p>", encoding="utf-8")
    css = tmp_path / "static" / "css"
    css.mkdir(parents=True)
    (css / "style.css").write_text(
        "background-image: url(\"data:image/svg+xml,%3Cfilter id='n'%3E%3C/filter%3E"
        "url(%23n)%3C/svg%3E\");\n",
        encoding="utf-8",
    )
    assert check_site(tmp_path, "/2daymovie") == []


def test_checker_accepts_prefixed_links(tmp_path: Path):
    (tmp_path / "index.html").write_text(
        """
        <link rel="stylesheet" href="/2daymovie/static/css/style.css" />
        <a href="/2daymovie/watch/621304">Watch</a>
        <div data-href="/2daymovie/watch/621304"></div>
        <form action="/2daymovie/year"></form>
        """,
        encoding="utf-8",
    )
    watch = tmp_path / "watch" / "621304"
    watch.mkdir(parents=True)
    (watch / "index.html").write_text("<p>ok</p>", encoding="utf-8")
    year = tmp_path / "year"
    year.mkdir()
    (year / "index.html").write_text('<a href="/2daymovie/watch/621304">2010</a>', encoding="utf-8")
    static_css = tmp_path / "static" / "css"
    static_css.mkdir(parents=True)
    (static_css / "style.css").write_text("", encoding="utf-8")

    assert check_site(tmp_path, "/2daymovie") == []
