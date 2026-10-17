"""Production app factory with health, readiness, Prometheus metrics, and SEO routes."""

from __future__ import annotations

import json
import os
import time

from dotenv import load_dotenv
from flask import Flask, Response, abort, g, jsonify, redirect, render_template, request, url_for
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from data.year_movies import all_years
from services import library, series, tmdb, upcoming, reviews
from services.search import search_catalog as unified_search

load_dotenv()

REQUESTS = Counter(
    "twodaymovie_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
LATENCY = Histogram(
    "twodaymovie_http_request_duration_seconds",
    "HTTP request latency",
    ["endpoint"],
)


def _hero_slides(limit: int = 8) -> list[dict]:
    """Curated trailer-ready movies for the home hero slideshow."""
    slides: list[dict] = []
    seen: set[int] = set()
    years = library.year_index()
    for entry in years[:6]:
        for movie in library.movies_for_year(entry["year"]):
            mid = movie.get("id")
            key = movie.get("trailer_key")
            backdrop = movie.get("backdrop")
            if not mid or mid in seen or not key or not backdrop:
                continue
            seen.add(mid)
            slides.append(
                {
                    "id": mid,
                    "title": movie.get("title") or "Trailer",
                    "year": movie.get("year"),
                    "trailer_key": key,
                    "backdrop": backdrop,
                    "poster": movie.get("poster"),
                    # url_for picks up SCRIPT_NAME, so GitHub Pages keeps /2daymovie.
                    "href": url_for("watch_page", movie_id=mid),
                }
            )
            if len(slides) >= limit:
                return slides
    return slides


class _ScriptPrefix:
    """Prefix generated links when the site is served from a subpath."""

    def __init__(self, wsgi_app, prefix: str):
        self.wsgi_app = wsgi_app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        environ["SCRIPT_NAME"] = self.prefix
        return self.wsgi_app(environ, start_response)


def _base_path() -> str:
    raw = os.getenv("BASE_PATH", "").strip().rstrip("/")
    if raw and not raw.startswith("/"):
        raw = "/" + raw
    return raw


def create_app() -> Flask:
    app = Flask(__name__)
    app.url_map.strict_slashes = False
    app.config["OFFICIAL_URL"] = os.getenv(
        "OFFICIAL_URL", "https://twodaymovie.onrender.com/"
    )
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "2daymovie-dev-secret-change-me")
    app.config["BASE_PATH"] = _base_path()
    app.config["STATIC_EXPORT"] = os.getenv("STATIC_EXPORT", "").strip() == "1"
    if app.config["BASE_PATH"]:
        app.wsgi_app = _ScriptPrefix(app.wsgi_app, app.config["BASE_PATH"])

    @app.before_request
    def _start_timer():
        g._start = time.perf_counter()

    @app.after_request
    def _record_metrics(response):
        try:
            endpoint = request.endpoint or "unknown"
            elapsed = time.perf_counter() - getattr(g, "_start", time.perf_counter())
            LATENCY.labels(endpoint=endpoint).observe(elapsed)
            REQUESTS.labels(
                method=request.method,
                endpoint=endpoint,
                status=str(response.status_code),
            ).inc()
        except Exception:
            pass
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            (
                "default-src 'self'; "
                "base-uri 'self'; "
                "object-src 'none'; "
                "frame-ancestors 'self'; "
                "img-src 'self' data: https://image.tmdb.org https://media.themoviedb.org https://i.ytimg.com; "
                "media-src 'self' https://image.tmdb.org; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "script-src 'self' 'unsafe-inline' https://www.youtube.com https://www.youtube-nocookie.com; "
                "frame-src https://www.youtube.com https://www.youtube-nocookie.com; "
                "connect-src 'self' https://www.youtube.com https://www.youtube-nocookie.com; "
                "form-action 'self'"
            ),
        )
        return response

    def catalog_url(
        kind: str,
        page: int = 1,
        sort: str = "rating",
        genre_id: int | None = None,
    ) -> str:
        page = max(1, int(page or 1))
        sort = sort or "rating"
        if kind == "genre":
            if sort != "rating" and page > 1:
                return url_for(
                    "genre_sorted_page", genre_id=genre_id, sort=sort, page=page
                )
            if sort != "rating":
                return url_for("genre_sorted", genre_id=genre_id, sort=sort)
            if page > 1:
                return url_for("genre_paged", genre_id=genre_id, page=page)
            return url_for("genre", genre_id=genre_id)
        if sort != "rating" and page > 1:
            return url_for("browse_sorted_page", sort=sort, page=page)
        if sort != "rating":
            return url_for("browse_sorted", sort=sort)
        if page > 1:
            return url_for("browse_paged", page=page)
        return url_for("browse")

    @app.context_processor
    def inject_globals():
        return {
            "site_name": "2daymovie",
            "live_api": tmdb.using_live_api(),
            "genres": tmdb.get_genres(),
            "library_years": all_years(),
            "official_url": app.config["OFFICIAL_URL"],
            "sort_options": library.SORT_OPTIONS,
            "static_export": app.config["STATIC_EXPORT"],
            "catalog_url": catalog_url,
            "page_description": (
                "Discover movies and TV shows on 2daymovie through official HD trailers. "
                "Browse by year, genre and title. We do not host or stream full films."
            ),
        }

    def _allowed_sorts() -> set[str]:
        return {key for key, _ in library.SORT_OPTIONS}

    def _sort_or_404(sort: str) -> str:
        if sort not in _allowed_sorts():
            abort(404)
        return sort

    def _search_index_json() -> str:
        items: list[dict] = []
        for movie in library.all_trailer_movies():
            items.append(
                {
                    "title": movie.get("title") or "",
                    "year": movie.get("year") or "",
                    "poster": movie.get("poster") or "",
                    "kind": "Movie",
                    "href": url_for("watch_page", movie_id=movie["id"]),
                }
            )
        for show in series.all_series_entries():
            if not show.get("id") or not show.get("trailer_key"):
                continue
            items.append(
                {
                    "title": show.get("title") or "",
                    "year": show.get("years") or show.get("start") or "",
                    "poster": show.get("poster") or "",
                    "kind": "Series",
                    "href": url_for("series_watch", tv_id=show["id"]),
                }
            )
        return json.dumps(items, ensure_ascii=True).replace("<", "\\u003c")

    def _catalog_similar(items, limit: int = 8) -> list[dict]:
        kept: list[dict] = []
        for item in items or []:
            try:
                sid = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            catalog = library.get_catalog_movie(sid)
            if not catalog or not catalog.get("trailer_key"):
                continue
            row = dict(item)
            for key in ("title", "poster", "year", "vote_average"):
                if catalog.get(key):
                    row[key] = catalog[key]
            kept.append(row)
            if len(kept) >= limit:
                break
        return kept

    def _page() -> int:
        try:
            value = int(request.args.get("page", 1))
        except (TypeError, ValueError):
            return 1
        return max(1, min(value, 500))

    def _sort() -> str:
        sort = request.args.get("sort", "rating")
        return sort if sort in _allowed_sorts() else "rating"

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok", service="2daymovie"), 200

    @app.get("/readyz")
    def readyz():
        stats = library.library_stats()
        ready = stats.get("resolved", 0) > 0
        payload = {"status": "ready" if ready else "not_ready", "library": stats}
        return jsonify(payload), (200 if ready else 503)

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    @app.get("/robots.txt")
    def robots():
        base = app.config["OFFICIAL_URL"].rstrip("/")
        content = f"""User-agent: *
Allow: /

Sitemap: {base}/sitemap.xml
"""
        return Response(content, mimetype="text/plain")

    @app.get("/sitemap.xml")
    def sitemap():
        base = app.config["OFFICIAL_URL"].rstrip("/")
        urls = [
            "/",
            "/movies",
            "/series",
            "/categories",
            "/upcoming",
            "/browse",
            "/about",
            "/search",
            "/reviews",
            "/year",
        ]
        urls.extend(f"/year/{year}" for year in all_years())
        urls.extend(
            f"/genre/{genre['id']}"
            for genre in tmdb.get_genres()
            if genre.get("id")
        )
        # High-value watch pages from the trailer catalog (capped for sitemap size)
        for movie in library.all_trailer_movies()[:400]:
            urls.append(f"/watch/{movie['id']}")
        for show in series.all_series_entries()[:120]:
            urls.append(f"/series/watch/{show['id']}")

        xml = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]
        for path in urls:
            xml.append(f"<url><loc>{base}{path}</loc></url>")
        xml.append("</urlset>")
        return Response("\n".join(xml), mimetype="application/xml")

    @app.route("/")
    def home():
        stats = library.library_stats()
        years = library.year_index()
        spotlight_year = years[0]["year"] if years else 2024
        spotlight = library.movies_for_year(spotlight_year)[:12]
        series_spotlight = [s for s in series.all_series_entries() if s.get("id")][:12]
        up = upcoming.upcoming_payload()
        featured = next((m for m in spotlight if m.get("backdrop")), None)
        hero_slides = _hero_slides(limit=8)
        latest_reviews = reviews.list_reviews(limit=6)
        review_stats = reviews.stats()
        series_stats = series.series_stats()
        return render_template(
            "index.html",
            featured=featured or (hero_slides[0] if hero_slides else None),
            hero_slides=hero_slides,
            stats=stats,
            spotlight_year=spotlight_year,
            spotlight=spotlight,
            series_spotlight=series_spotlight,
            upcoming_movies=up["movies"][:8],
            upcoming_movies_2027=up["movies_2027"][:8],
            upcoming_series=up["series"][:8],
            latest_reviews=latest_reviews,
            review_stats=review_stats,
            series_stats=series_stats,
            meta_title="2daymovie — Official HD Movie & TV Trailers",
            meta_description=(
                "Discover movies and TV shows on 2daymovie through official HD trailers. "
                "Browse by year, genre and title."
            ),
        )

    @app.route("/about")
    def about():
        return render_template(
            "about.html",
            meta_title="About 2daymovie — Created by Arnold Rurangwa",
            meta_description=(
                "2daymovie is a movie and TV trailer discovery platform created and developed "
                "by Arnold Rurangwa. Official HD trailers only."
            ),
        )

    @app.route("/reviews", methods=["GET", "POST"])
    def reviews_home():
        notice = request.args.get("thanks")
        error = None
        form = {"name": "", "rating": "5", "message": ""}
        if request.method == "POST":
            form = {
                "name": request.form.get("name", ""),
                "rating": request.form.get("rating", "5"),
                "message": request.form.get("message", ""),
            }
            review, error = reviews.add_review(
                name=form["name"],
                rating=form["rating"],
                message=form["message"],
                ip=(request.headers.get("X-Forwarded-For") or request.remote_addr or "")
                .split(",")[0]
                .strip(),
                honeypot=request.form.get("website", ""),
            )
            if review and not error:
                return redirect(url_for("reviews_home", thanks="1"))
        return render_template(
            "reviews.html",
            reviews=reviews.list_reviews(limit=40),
            stats=reviews.stats(),
            form=form,
            error=error,
            notice="Thanks — your review is live." if notice else None,
            meta_title="Live Reviews | 2daymovie",
            meta_description="Read and leave live visitor reviews for 2daymovie.",
        )

    @app.get("/api/reviews")
    def reviews_api():
        rows = reviews.list_reviews(limit=40)
        return jsonify({"reviews": rows, "stats": reviews.stats()})

    @app.route("/upcoming")
    def upcoming_home():
        payload = upcoming.upcoming_payload()
        return render_template(
            "upcoming.html",
            movies_2025=payload.get("movies_2025") or [],
            movies=payload["movies"],
            movies_2027=payload["movies_2027"],
            shows=payload["series"],
            movie_count=payload["movie_count"],
            series_count=payload["series_count"],
            with_trailer=payload["with_trailer"],
            meta_title="Upcoming Movies & Series 2025–2027 | 2daymovie",
            meta_description=(
                "Browse upcoming 2025–2027 movies and series on 2daymovie. "
                "On-site trailers when available."
            ),
        )

    @app.route("/categories")
    def categories_home():
        return render_template(
            "categories.html",
            genres=tmdb.get_genres(),
            meta_title="Categories · Genres | 2daymovie",
            meta_description="Browse movies by genre on 2daymovie. Action, Drama, Animation, Sci-Fi, Horror, and more.",
        )

    def _render_movies(selected, strict: bool = False):
        shelf = library.movies_shelf(selected)
        if strict and selected is not None and shelf["selected_year"] != selected:
            abort(404)
        return render_template(
            "movies.html",
            stats=library.library_stats(),
            years=shelf["years"],
            selected_year=shelf["selected_year"],
            movies=shelf["movies"],
            meta_title="Movies by Year | 2daymovie",
            meta_description="Browse curated movies from classic cinema through 2027 with on-site official trailers on 2daymovie.",
        )

    @app.route("/movies")
    def movies_home():
        year_arg = request.args.get("year")
        selected = None
        if year_arg:
            try:
                selected = int(year_arg)
            except (TypeError, ValueError):
                selected = None
        return _render_movies(selected)

    @app.route("/movies/year/<int:year>")
    def movies_year(year: int):
        return _render_movies(year, strict=True)

    @app.route("/library")
    def library_home():
        year = request.args.get("year")
        if year:
            return redirect(url_for("movies_home", year=year))
        return redirect(url_for("movies_home"))

    def _render_series(selected, strict: bool = False):
        shelf = series.series_shelf(selected)
        if strict and selected is not None and shelf["selected_year"] != selected:
            abort(404)
        return render_template(
            "series.html",
            stats=series.series_stats(),
            years=shelf["years"],
            selected_year=shelf["selected_year"],
            shows=shelf["shows"],
            meta_title="TV Series | 2daymovie",
            meta_description="Browse curated TV series with on-site official trailers on 2daymovie.",
        )

    @app.route("/series")
    def series_home():
        year_arg = request.args.get("year")
        selected = None
        if year_arg:
            try:
                selected = int(year_arg)
            except (TypeError, ValueError):
                selected = None
        return _render_series(selected)

    @app.route("/series/year/<int:year>")
    def series_year(year: int):
        return _render_series(year, strict=True)

    @app.route("/series/watch/<int:tv_id>")
    def series_watch(tv_id: int):
        show = series.get_series(tv_id)
        if show is None or not show.get("trailer_key"):
            abort(404)
        return render_template(
            "series_watch.html",
            show=show,
            meta_title=f"{show['title']} — Official HD Trailer | 2daymovie",
            meta_description=(
                f"Watch the official HD trailer for {show['title']} on 2daymovie."
            ),
        )

    @app.get("/year")
    def year_jump():
        raw = (request.args.get("year") or "").strip().rstrip("/")
        if not raw:
            # Static hosts have no redirect server. The exported page reads
            # ?year= and sends the browser to /year/<year>.
            return render_template(
                "year_index.html",
                years=all_years(),
                meta_title="Movies by Year | 2daymovie",
                meta_description="Choose a year to browse official HD trailers on 2daymovie.",
            )
        try:
            year = int(raw)
        except (TypeError, ValueError):
            abort(404)
        if year not in all_years():
            abort(404)
        return redirect(url_for("year_page", year=year))

    @app.route("/year/<int:year>")
    def year_page(year: int):
        if year not in all_years():
            abort(404)
        movies = library.movies_for_year(year)
        return render_template(
            "year.html",
            year=year,
            movies=movies,
            years=all_years(),
            count=len(movies),
            with_trailer=len(movies),
            meta_title=f"Movies of {year} | 2daymovie",
            meta_description=(
                f"Browse movies from {year} on 2daymovie. Discover titles, "
                f"official HD trailers and ratings."
            ),
        )

    @app.route("/watch/<int:movie_id>")
    def watch_page(movie_id: int):
        movie = library.get_catalog_movie(movie_id)
        if movie is None or not movie.get("trailer_key"):
            abort(404)
        # Enrich details from TMDB when API key is present
        detail = tmdb.get_movie(movie_id)
        if detail:
            for key in (
                "runtime",
                "tagline",
                "genres",
                "providers",
                "cast",
                "similar",
                "watch_link",
            ):
                if detail.get(key):
                    movie[key] = detail[key]
            movie["similar"] = _catalog_similar(movie.get("similar"))
            if detail.get("overview") and len(detail["overview"]) > len(
                movie.get("overview") or ""
            ):
                movie["overview"] = detail["overview"]
        year = movie.get("year") or ""
        title = movie.get("title") or "Movie"
        return render_template(
            "watch.html",
            movie=movie,
            meta_title=f"{title} ({year}) — Official HD Trailer | 2daymovie",
            meta_description=(
                f"Watch the official HD trailer for {title} ({year}) on 2daymovie."
            ),
        )

    def _render_browse(page: int, sort: str):
        page = max(1, min(int(page or 1), 500))
        payload = library.browse_catalog(page=page, sort=sort)
        return render_template(
            "browse.html",
            movies=payload["results"],
            page=payload["page"],
            total_pages=payload["total_pages"],
            total_results=payload["total_results"],
            sort=payload["sort"],
            meta_title="Catalog · All Trailers | 2daymovie",
            meta_description=(
                f"Browse {payload['total_results']} movies with on-site trailers on 2daymovie."
            ),
        )

    @app.route("/browse")
    def browse():
        return _render_browse(_page(), _sort())

    @app.route("/browse/page/<int:page>")
    def browse_paged(page: int):
        return _render_browse(page, "rating")

    @app.route("/browse/sort/<sort>")
    def browse_sorted(sort: str):
        return _render_browse(_page(), _sort_or_404(sort))

    @app.route("/browse/sort/<sort>/page/<int:page>")
    def browse_sorted_page(sort: str, page: int):
        return _render_browse(page, _sort_or_404(sort))

    @app.route("/search")
    def search():
        query = request.args.get("q", "").strip()
        page = _page()
        payload = (
            unified_search(query, page=page)
            if query
            else {"results": [], "page": 1, "total_pages": 1, "total_results": 0}
        )
        results = []
        for item in payload["results"]:
            row = dict(item)
            if row.get("media_type") == "tv":
                row["result_type"] = "series"
                row["year"] = row.get("years") or row.get("start")
                row["href"] = url_for("series_watch", tv_id=row["id"])
            else:
                row["result_type"] = "movie"
                row["href"] = url_for("watch_page", movie_id=row["id"])
            results.append(row)
        return render_template(
            "search.html",
            query=query,
            results=results,
            page=payload["page"],
            total_pages=payload["total_pages"],
            total_results=payload["total_results"],
            search_index_json=_search_index_json() if app.config["STATIC_EXPORT"] else "[]",
            meta_title=(f"“{query}” · Search | 2daymovie" if query else "Search | 2daymovie"),
            meta_description="Search movies and TV series with on-site trailers on 2daymovie.",
        )

    def _render_genre(genre_id: int, page: int, sort: str):
        name = tmdb.genre_name(genre_id)
        if name.lower() in {"adult", "nc-17"}:
            abort(404)
        page = max(1, min(int(page or 1), 500))
        payload = library.movies_by_genre(genre_id, page=page, sort=sort)
        return render_template(
            "genre.html",
            genre_name=name,
            genre_id=genre_id,
            movies=payload["results"],
            page=payload["page"],
            total_pages=payload["total_pages"],
            total_results=payload["total_results"],
            sort=payload["sort"],
            meta_title=f"{name} Movies | 2daymovie",
            meta_description=(
                f"Browse {name} movies with on-site trailers on 2daymovie. "
                f"{payload['total_results']} titles in this category."
            ),
        )

    @app.route("/genre/<int:genre_id>")
    def genre(genre_id: int):
        return _render_genre(genre_id, _page(), _sort())

    @app.route("/genre/<int:genre_id>/page/<int:page>")
    def genre_paged(genre_id: int, page: int):
        return _render_genre(genre_id, page, "rating")

    @app.route("/genre/<int:genre_id>/sort/<sort>")
    def genre_sorted(genre_id: int, sort: str):
        return _render_genre(genre_id, _page(), _sort_or_404(sort))

    @app.route("/genre/<int:genre_id>/sort/<sort>/page/<int:page>")
    def genre_sorted_page(genre_id: int, sort: str, page: int):
        return _render_genre(genre_id, page, _sort_or_404(sort))

    @app.route("/movie/<int:movie_id>")
    def movie_details(movie_id: int):
        # Prefer catalog trailer titles; fall back to TMDB detail only if in catalog
        movie = library.get_catalog_movie(movie_id)
        if movie is None:
            abort(404)
        detail = tmdb.get_movie(movie_id)
        if detail:
            catalog_keys = list(movie.get("trailer_keys") or [])
            detail_keys = list(detail.get("trailer_keys") or [])
            movie = {**detail, **movie}
            merged = []
            seen = set()
            for key in catalog_keys + detail_keys + [movie.get("trailer_key"), detail.get("trailer_key")]:
                if key and key not in seen:
                    seen.add(key)
                    merged.append(key)
            movie["trailer_keys"] = merged
            movie["trailer_key"] = merged[0] if merged else None
            movie["similar"] = _catalog_similar(movie.get("similar"))
        if not movie.get("trailer_key"):
            abort(404)
        year = movie.get("year") or ""
        title = movie.get("title") or "Movie"
        return render_template(
            "movie.html",
            movie=movie,
            meta_title=f"{title} ({year}) — Official HD Trailer | 2daymovie",
            meta_description=(
                f"Discover {title} ({year}) on 2daymovie. View details and the official HD trailer."
            ),
        )

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
