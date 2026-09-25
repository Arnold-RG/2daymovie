"""2daymovie.to — legal movie discovery platform (browse, trailers, where to watch)."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask, abort, render_template, request

from services import tmdb

load_dotenv()

app = Flask(__name__)


def _page() -> int:
    try:
        value = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        return 1
    return max(1, min(value, 500))


@app.context_processor
def inject_globals():
    return {
        "site_name": "2daymovie.to",
        "live_api": tmdb.using_live_api(),
        "genres": tmdb.get_genres(),
    }


@app.route("/")
def home():
    trending = tmdb.get_trending()
    popular = tmdb.get_popular()
    now_playing = tmdb.get_now_playing()
    top_rated = tmdb.get_top_rated()
    featured = trending["results"][0] if trending["results"] else None
    return render_template(
        "index.html",
        featured=featured,
        rows=[
            ("Trending this week", trending["results"]),
            ("Popular", popular["results"]),
            ("Now playing", now_playing["results"]),
            ("Top rated", top_rated["results"]),
        ],
    )


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
    payload = tmdb.search_movies(query, page=page) if query else {
        "results": [],
        "page": 1,
        "total_pages": 1,
        "total_results": 0,
    }
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


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
