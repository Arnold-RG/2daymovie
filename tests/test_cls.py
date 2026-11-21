"""Layout-shift guards for the first screen (Lighthouse CLS 0.42-0.46 after PR #40, ~0 after this fix).

The catalogue starts inside the first screen on phones (below the 16:9 hero band), so anything that
changes size or position there when JavaScript runs counts as a layout shift. These checks keep the
server HTML and the JS-rendered page the same shape."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "templates/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "static/css/app.css").read_text(encoding="utf-8")
APP = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
HERO = (ROOT / "static/js/hero.js").read_text(encoding="utf-8")


def test_browse_ships_skeleton_rows_that_hold_the_first_screen():
    browse = HTML[HTML.index('<div id="browse">'):HTML.index('<section class="results"')]
    assert 'class="skel" id="browseSkeleton" aria-hidden="true"' in browse
    assert browse.count('class="tile tile--trailer"') >= 3 and browse.count('<div class="tile">') >= 4
    assert ".skel { min-height: 100vh; min-height: 100svh;" in CSS
    assert 'root.textContent = "";' in APP  # renderBrowse replaces the skeleton


def test_loading_text_margin_cannot_collapse_through_main():
    assert re.search(r"\.loading \{[^}]*margin: 0;", CSS)


def test_release_countdown_has_a_reserved_slot():
    assert '<span class="hero__date-count is-placeholder" aria-hidden="true">in 00 days</span>' in HTML
    assert ".hero__date-count.is-placeholder { visibility: hidden; }" in CSS
    assert 'date.querySelector(".hero__date-count.is-placeholder")' in HERO


def test_tab_bar_glass_keeps_its_box_when_the_bump_is_drawn():
    assert ".tabbar__glass { position: absolute; left: 0; right: 0; top: 0; bottom: 0;" in CSS
    assert "clip-path: inset(var(--tab-bump) 0 0 0 round 24px)" in CSS
    assert ".tabbar__glass.has-bump { border-radius: 0; box-shadow: none; }" in CSS


def test_first_poster_is_server_rendered_preloaded_and_adopted():
    track = HTML[HTML.index('<div class="hero__track" id="heroTrack">'):HTML.index('<div class="hero__shade">')]
    assert 'class="slide__poster hero__ssr-poster" data-id="{{ hero.id }}"' in track and 'fetchpriority="high"' in track
    assert 'rel="preload" as="image"' in HTML and 'imagesizes="(max-width: 900px) 50vw, 100vw"' in HTML
    assert 'track.querySelector(`.hero__ssr-poster[data-id="${t.id}"]`)' in HERO
    assert ".hero__ssr-poster { transform: scale(1.02);" in CSS  # same as the Ken Burns start: no bigger, later LCP


def test_catalog_waits_for_the_hero_poster():
    assert 'posterFirst.then(() => fetch(base + "data/catalog.json"' in APP
    assert "setTimeout(resolve, 1500)" in APP


def test_reveal_timers_are_cleared_when_a_slide_is_left_or_paused():
    assert "if (prev) { prev.wantPlay = false; clearTimeout(prev.reveal);" in HERO
    assert "clearTimeout(p.reveal); // a pending fade-in must not outlive the pause" in HERO


def test_reduced_motion_drops_the_video_fade():
    rm = CSS[CSS.index("@media (prefers-reduced-motion: reduce) {"):]
    assert ".slide__video, .slide__video.is-playing { transition: none; }" in rm
