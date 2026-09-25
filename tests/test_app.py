from app import app
from services import library


def test_home_ok():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"2daymovie" in response.data
    assert b"Upcoming" in response.data
    assert b"data-hero-slider" in response.data or b"hero" in response.data


def test_browse_ok():
    client = app.test_client()
    response = client.get("/browse")
    assert response.status_code == 200
    assert b"Sort by" in response.data


def test_movie_details_ok():
    client = app.test_client()
    movie = library.get_catalog_movie(27205)
    assert movie is not None
    response = client.get("/movie/27205")
    assert response.status_code == 200
    assert b"Inception" in response.data


def test_movie_not_found():
    client = app.test_client()
    response = client.get("/movie/999999999")
    assert response.status_code == 404


def test_search():
    client = app.test_client()
    response = client.get("/search?q=inception")
    assert response.status_code == 200
    assert b"Inception" in response.data


def test_movies_ok():
    client = app.test_client()
    response = client.get("/movies")
    assert response.status_code == 200
    assert b"Movies" in response.data
    assert b"2000" in response.data or b"2024" in response.data or b"2026" in response.data


def test_categories_ok():
    client = app.test_client()
    response = client.get("/categories")
    assert response.status_code == 200
    assert b"Categories" in response.data
    assert b"Action" in response.data or b"Drama" in response.data


def test_genre_sort():
    client = app.test_client()
    response = client.get("/genre/28?sort=newest")
    assert response.status_code == 200
    assert b"Sort by" in response.data
    assert b"selected" in response.data


def test_library_redirects():
    client = app.test_client()
    response = client.get("/library")
    assert response.status_code in (301, 302)
    assert "/movies" in response.headers.get("Location", "")


def test_year_page_ok():
    client = app.test_client()
    response = client.get("/year/2010")
    assert response.status_code == 200
    assert b"Inception" in response.data


def test_upcoming_ok():
    client = app.test_client()
    response = client.get("/upcoming")
    assert response.status_code == 200
    assert b"Upcoming" in response.data


def test_about_ok():
    client = app.test_client()
    response = client.get("/about")
    assert response.status_code == 200
    assert b"Arnold Rurangwa" in response.data
    assert b"GitHub" not in response.data


def test_robots_and_sitemap():
    client = app.test_client()
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert b"Sitemap:" in robots.data
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert b"<urlset" in sitemap.data
    assert b"/about" in sitemap.data


def test_healthz():
    client = app.test_client()
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_readyz():
    client = app.test_client()
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ready"


def test_metrics():
    client = app.test_client()
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"twodaymovie_http_requests_total" in response.data


def test_series_ok():
    client = app.test_client()
    response = client.get("/series")
    assert response.status_code == 200
    assert b"Series" in response.data
    response_2002 = client.get("/series?year=2002")
    assert response_2002.status_code == 200
    assert b"The Wire" in response_2002.data or b"The Shield" in response_2002.data


def test_security_headers():
    client = app.test_client()
    response = client.get("/")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"


def test_reviews_live(tmp_path, monkeypatch):
    reviews_file = tmp_path / "reviews.json"
    monkeypatch.setenv("REVIEWS_PATH", str(reviews_file))
    # reload path resolution by clearing rate map and using fresh path
    from services import reviews as reviews_mod

    reviews_mod._RATE.clear()

    client = app.test_client()
    page = client.get("/reviews")
    assert page.status_code == 200
    assert b"Live reviews" in page.data

    posted = client.post(
        "/reviews",
        data={
            "name": "Alex",
            "rating": "5",
            "message": "Great trailers on this site!",
            "website": "",
        },
        follow_redirects=False,
    )
    assert posted.status_code in (301, 302)

    api = client.get("/api/reviews")
    assert api.status_code == 200
    payload = api.get_json()
    assert payload["stats"]["count"] >= 1
    assert any(r["name"] == "Alex" for r in payload["reviews"])

    home = client.get("/")
    assert home.status_code == 200
    assert b"Live reviews" in home.data
    assert b"Alex" in home.data
