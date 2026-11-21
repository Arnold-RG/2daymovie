"""Phone layout and the floating glass tab bar (static checks; the headless runs live in qa/)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "templates/index.html").read_text(encoding="utf-8")
CSS = (ROOT / "static/css/app.css").read_text(encoding="utf-8")
MOB = (ROOT / "static/js/mobile.js").read_text(encoding="utf-8")
APP = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
HERO = (ROOT / "static/js/hero.js").read_text(encoding="utf-8")
PHONE = "(max-width: 900px), (max-width: 1000px) and (max-height: 500px)"


def test_tab_bar_is_a_labelled_nav_with_five_slots_and_a_centre_search():
    nav = HTML[HTML.index('<nav class="tabbar"'):HTML.index("</nav>", HTML.index('<nav class="tabbar"'))]
    assert 'aria-label="Quick navigation"' in nav
    tabs = re.findall(r'data-tab="(\w+)"', nav)
    assert tabs == ["home", "browse", "search", "kids", "mylist"]
    assert 'class="tab tab--center" type="button" data-tab="search" aria-label="Search"' in nav
    # Shuffle moved into the Browse sheet; Kids falls back to Upcoming Trailers if the section is missing
    assert 'data-shuffle' in HTML and '[data-shuffle]' in MOB
    assert 'k.dataset.tab = "trailers"' in MOB
    assert 'aria-current="page"' in nav and 'id="listBadge"' in nav


def test_tab_bar_floats_as_glass_with_a_red_glow_and_safe_areas():
    assert "--tab-gap: 12px; --tab-side: 12px;" in CSS
    assert "backdrop-filter: blur(20px)" in CSS and "-webkit-backdrop-filter: blur(20px)" in CSS
    assert "env(safe-area-inset-bottom" in CSS and "env(safe-area-inset-left" in CSS
    assert 'stop-color="#ff4b54"' in HTML and "drop-shadow(0 0 3px rgba(229,9,20,.9))" in CSS
    assert "function barShape(" in MOB and "glass.style.clipPath" in MOB


def test_targets_are_at_least_48px_and_reduced_motion_is_respected():
    assert re.search(r"\.tab \{[^}]*min-width: 48px; min-height: 48px;", CSS)
    assert ".shuffle-btn {" in CSS and "min-height: 48px" in CSS
    assert ".chip { display: inline-flex; align-items: center; gap: 8px; min-height: 48px;" in CSS
    rm = CSS[CSS.index("@media (prefers-reduced-motion: reduce)"):]
    assert ".tabbar, .tab, .tabbar__dot, .sheet__panel" in rm and "transition: none !important" in rm


def test_hide_on_scroll_dot_indicator_long_press_and_sheets():
    assert 'bar.classList.add("is-hidden")' in MOB and "holdUntil" in MOB
    assert "function moveDot()" in MOB and ".tabbar__dot.is-on { opacity: 1; }" in CSS
    assert "LONG_PRESS_MS" in MOB and 'jump("trailers")' in MOB
    for sid in ("sheetSearch", "sheetGenres", "sheetList"):
        assert f'id="{sid}" role="dialog" aria-modal="true"' in HTML
    assert 'e.key === "Escape"' in MOB and 'e.key === "Tab"' in MOB  # close + focus trap
    assert 'chip("Upcoming Trailers", "trailers"' in MOB


def test_my_list_hearts_are_sibling_buttons_and_stay_local():
    assert 'el("button", "heart")' in APP and "w.appendChild(card(v, opts));" in APP
    assert 'const LIST_KEY = "tdm.mylist.v1";' in APP
    assert "tdm.mylist.v1" in HTML  # privacy note names the key
    assert "Your list is empty" in HTML


def test_phone_layout_fills_the_screen_and_fits_2_3_posters():
    assert f"@media {PHONE} {{" in CSS
    assert ".hero, .hero[data-size] { height: 100vh; height: 100svh; min-height: 0; }" in CSS
    assert ".tile { width: clamp(132px, 42vw, 230px); }" in CSS
    assert ".hero[data-size] .hero__title { font-size: clamp(26px, 8.2vw, 38px);" in CSS
    assert ".nav__toggle, .nav__links, .nav .search { display: none !important; }" in CSS
    assert "let size = !phoneLayout && SIZES.includes(saved.size)" in HERO and PHONE in HERO


def test_neighbour_trailers_wait_for_the_first_one_to_play():
    assert "const NEIGHBOUR_MS = 8000;" in HERO
    assert "if (p && p.playing) warmNeighbours();" in HERO and "if (i === cur) { warmNeighbours(); startFirstTimer(); }" in HERO


def test_first_slide_countdown_waits_for_its_trailer():
    assert "const FIRST_WAIT_MS = 15000;" in HERO
    assert "firstWait = setTimeout(startFirstTimer, FIRST_WAIT_MS);" in HERO
    assert "if (i === cur) { warmNeighbours(); startFirstTimer(); }" in HERO
    assert "if (!reduceMotion.matches && timerOn) raf = requestAnimationFrame(tick);" in HERO
