"""Production app factory with health, readiness, and Prometheus metrics."""

from __future__ import annotations

import os
import time

from dotenv import load_dotenv
from flask import Flask, Response, abort, g, jsonify, render_template, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from data.year_movies import all_years
from services import library, tmdb

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


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["OFFICIAL_URL"] = os.getenv(
        "OFFICIAL_URL", "https://twodaymovie.onrender.com/"
    )

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
        return response

    @app.context_processor
    def inject_globals():
        return {
            "site_name": "2daymovie.to",
            "live_api": tmdb.using_live_api(),
            "genres": tmdb.get_genres(),
            "library_years": all_years(),
            "official_url": app.config["OFFICIAL_URL"],
        }

    def _page() -> int:
        try:
            value = int(request.args.get("page", 1))
        except (TypeError, ValueError):
            return 1
        return max(1, min(value, 500))

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

    @app.route("/")
    def home():
        stats = library.library_stats()
        years = library.year_index()
        spotlight_year = years[0]["year"] if years else 2024
        spotlight = library.movies_for_year(spotlight_year)[:12]
        trending = tmdb.get_trending()
        featured = next((m for m in spotlight if m.get("backdrop")), None) or (
            trending["results"][0] if trending["results"] else None
        )
        return render_template(
            "index.html",
            featured=featured,
            stats=stats,
            year_cards=years,
            spotlight_year=spotlight_year,
            spotlight=spotlight,
            rows=[
                (f"Library spotlight · {spotlight_year}", spotlight),
                ("Trending this week", trending["results"]),
            ],
        )

    @app.route("/library")
    def library_home():
        return render_template(
            "library.html",
            stats=library.library_stats(),
            years=library.year_index(),
        )

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
            with_trailer=sum(1 for m in movies if m.get("trailer_key")),
        )

    @app.route("/watch/<int:movie_id>")
    def watch_page(movie_id: int):
        movie = tmdb.get_movie(movie_id)
        catalog_hit = None
        for row in library._load_resolved():
            if row.get("id") == movie_id:
                catalog_hit = library._normalize_entry(row)
                break
        if movie is None:
            movie = catalog_hit
        elif catalog_hit:
            if not movie.get("trailer_key") and catalog_hit.get("trailer_key"):
                movie["trailer_key"] = catalog_hit["trailer_key"]
            if not movie.get("year") and catalog_hit.get("year"):
                movie["year"] = catalog_hit["year"]
        if movie is None:
            abort(404)
        movie["watch_link"] = movie.get("watch_link") or tmdb.legal_watch_url(movie_id)
        return render_template("watch.html", movie=movie)

    @app.route("/browse")
    def browse():
        page = _page()
        sort = request.args.get("sort", "popularity.desc")
        allowed = {
            "popularity.desc",
            "vote_average.desc",
            "primary_release_date.desc",
            "revenue.desc",
        }
        if sort not in allowed:
            sort = "popularity.desc"
        payload = tmdb.discover_movies(page=page, sort_by=sort)
        return render_template(
            "browse.html",
            movies=payload["results"],
            page=payload["page"],
            total_pages=payload["total_pages"],
            total_results=payload["total_results"],
            sort=sort,
        )

    @app.route("/search")
    def search():
        query = request.args.get("q", "").strip()
        page = _page()
        payload = (
            tmdb.search_movies(query, page=page)
            if query
            else {"results": [], "page": 1, "total_pages": 1, "total_results": 0}
        )
        return render_template(
            "search.html",
            query=query,
            results=payload["results"],
            page=payload["page"],
            total_pages=payload["total_pages"],
            total_results=payload["total_results"],
        )

    @app.route("/genre/<int:genre_id>")
    def genre(genre_id: int):
        page = _page()
        payload = tmdb.discover_by_genre(genre_id, page=page)
        name = tmdb.genre_name(genre_id)
        return render_template(
            "genre.html",
            genre_name=name,
            genre_id=genre_id,
            movies=payload["results"],
            page=payload["page"],
            total_pages=payload["total_pages"],
            total_results=payload["total_results"],
        )

    @app.route("/movie/<int:movie_id>")
    def movie_details(movie_id: int):
        movie = tmdb.get_movie(movie_id)
        if movie is None:
            abort(404)
        return render_template("movie.html", movie=movie)

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("404.html"), 404

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
