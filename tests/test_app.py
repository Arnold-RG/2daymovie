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


def test_genre_page():
    client = app.test_client()
    response = client.get("/genre/878")
    assert response.status_code == 200
