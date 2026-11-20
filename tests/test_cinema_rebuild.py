"""Smoke/regression checks for the new cinema homepage and release radar."""
from app import create_app
from data.release_window import WINDOW_RELEASES


def test_homepage_cinema_sections_and_embed_controls():
    client = create_app().test_client()
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Cinema without" in html
    assert "Featured movie previews" in html
    assert "The release radar" in html
    assert "today-cinema.js" in html
    assert "tm-feature-player" in html
    # We must not load a video iframe until visitors choose to play.
    assert 'id="tm-feature-player"' in html
    assert "data-tm-video=" in html or "New screening experiences are coming" in html
    assert "No unverified full films" in html


def test_release_window_is_in_requested_months_and_unique():
    assert WINDOW_RELEASES
    dates = [row["date"] for row in WINDOW_RELEASES]
    assert dates == sorted(dates)
    assert all("2026-12-01" <= d <= "2027-03-31" for d in dates)
    assert len({row["title"] for row in WINDOW_RELEASES}) == len(WINDOW_RELEASES)


def test_upcoming_page_shows_release_window():
    response = create_app().test_client().get("/upcoming")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Avengers: Doomsday" in body
    assert "Sonic the Hedgehog 4" in body
    assert "Cinema United" in body


def test_homepage_has_security_headers():
    response = create_app().test_client().get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-src https://www.youtube.com https://www.youtube-nocookie.com" in response.headers["Content-Security-Policy"]
