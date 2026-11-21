"""Fixes from the Sentinel QA review of PR #38 (static checks)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "templates/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "static/css/app.css").read_text(encoding="utf-8")
APP = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
HERO = (ROOT / "static/js/hero.js").read_text(encoding="utf-8")


def test_background_embed_asks_for_muted_inline_autoplay():
    assert "autoplay: i === cur ? 1 : 0, mute: 1" in HERO
    assert "playsinline: 1" in HERO


def test_youtube_player_starts_after_load_not_before_lcp():
    assert 'window.addEventListener("load", idle, { once: true })' in HERO
    assert "requestIdleCallback(startVideo" in HERO


def test_first_slide_is_in_the_html_and_reused():
    hero = HTML[HTML.index('id="heroContent"'):HTML.index("</section>", HTML.index('id="heroContent"'))]
    assert 'data-ssr="{{ hero.id }}"' in hero and "hero__title hero__logo" in hero
    assert "content.dataset.ssr" in HERO


def test_poster_falls_back_when_maxres_is_missing():
    assert 't.poster || "maxresdefault"' in HERO
    assert "hqdefault" in HERO and "naturalWidth" in HERO


def test_pause_button_is_first_in_hero_tab_order():
    sec = HTML[HTML.index('<section class="hero"'):]
    first_control = re.search(r'<(button|a)\b[^>]*>', sec)
    assert 'id="heroPause"' in sec[:sec.index('id="heroContent"')]
    assert first_control and "hero__cue" not in first_control.group(0)


def test_phone_hero_stays_full_height_with_a_scroll_cue_and_progress_line():
    assert 'class="hero__cue" href="#trailers"' in HTML
    assert ".hero, .hero[data-size] { height: 100vh; height: 100svh; min-height: 0; }" in CSS
    assert "  .hero__dots { display: none; }" in CSS
    assert ".hero__dot { position: relative; flex: 0 0 auto; width: 24px; height: 24px;" in CSS


def test_search_inputs_show_focus_and_tab_labels_are_readable():
    assert ".search input:focus-visible { outline: 2px solid #fff;" in CSS
    assert ".sheet__search input:focus-visible { outline: 2px solid #fff;" in CSS
    assert "9.5px" not in CSS


def test_offscreen_rows_are_filled_lazily_with_reserved_height():
    assert "IntersectionObserver" in APP and "EAGER_ROWS" in APP
    assert ".row__scroller.is-lazy { min-height:" in CSS


def test_explore_index_redirects_to_movies():
    assert '@app.get("/explore/")' in (ROOT / "app.py").read_text(encoding="utf-8")
    page = (ROOT / "templates/explore.html").read_text(encoding="utf-8")
    assert 'http-equiv="refresh"' in page and "explore/movies/" in page and "noindex" in page
    bp = (ROOT / "render.yaml").read_text(encoding="utf-8")
    site = bp[bp.index("name: 2daymovie-site"):]
    nxt = site.find("\n  - type:", 1)
    site = site if nxt < 0 else site[:nxt]
    assert "routes:" in site and "source: /explore/" in site and "destination: /explore/movies/" in site
    for h in ("Referrer-Policy", "Permissions-Policy", "Content-Security-Policy"):
        assert f"name: {h}" in site
    assert "frame-ancestors 'none'" in site


def test_ci_compose_check_has_a_placeholder_password():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "GRAFANA_ADMIN_PASSWORD: ci-validation-only" in ci
