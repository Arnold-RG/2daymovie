from app import app


def test_home_ok():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"2daymovie.to" in response.data


def test_browse_ok():
    client = app.test_client()
    response = client.get("/browse")
    assert response.status_code == 200


def test_movie_details_ok():
    client = app.test_client()
    response = client.get("/movie/27205")
    assert response.status_code == 200
    assert b"Inception" in response.data


def test_movie_not_found():
    client = app.test_client()
    response = client.get("/movie/999999999")
    assert response.status_code == 404


def test_search():
    client = app.test_client()
    response = client.get("/search?q=matrix")
    assert response.status_code == 200
    assert b"The Matrix" in response.data


def test_movies_ok():
    client = app.test_client()
    response = client.get("/movies")
    assert response.status_code == 200
    assert b"Movies" in response.data
    assert b"2000" in response.data or b"2024" in response.data


def test_categories_ok():
    client = app.test_client()
    response = client.get("/categories")
    assert response.status_code == 200
    assert b"Categories" in response.data
    assert b"Action" in response.data or b"Drama" in response.data


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
