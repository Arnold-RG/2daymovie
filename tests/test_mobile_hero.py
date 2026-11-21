"""Portrait phones: a 16:9 video band with the text stacked below it (static checks; Playwright runs live in qa/)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "static/css/app.css").read_text(encoding="utf-8")
APP = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
BAND = "@media (max-width: 900px) and (max-aspect-ratio: 4/3) {"


def block(start):
    i = CSS.index(start)
    depth, j = 0, i
    while True:
        c = CSS[j]
        depth += c == "{"
        depth -= c == "}"
        j += 1
        if depth == 0 and c == "}":
            return CSS[i:j]


def test_band_height_is_clamped_to_the_small_viewport_with_a_vh_fallback():
    assert ":root { --band-h: clamp(150px, 56.25vw, 46vh); }" in CSS
    assert "@supports (height: 1svh) { :root { --band-h: clamp(150px, 56.25vw, 46svh); } }" in CSS


def test_portrait_phones_stack_text_below_the_band_in_normal_flow():
    b = block(BAND)
    assert "height: auto; min-height: 0; display: flex; flex-direction: column;" in b
    assert ".hero__track, .hero__shade { inset: auto; top: var(--nav-h); left: 0; right: 0; height: var(--band-h); }" in b
    assert ".hero__content { position: relative; inset: auto;" in b and "gap: 8px;" in b
    assert ".hero__bar { top: calc(var(--nav-h) + 8px); bottom: auto;" in b
    assert ".hero__progress { top: calc(var(--nav-h) + var(--band-h) - 3px); bottom: auto;" in b


def test_hero_controls_and_buttons_are_44px_on_small_screens():
    assert "  .hbtn { width: 38px" not in CSS
    assert "  .hbtn { width: 44px; height: 44px; border-radius: 12px; }" in CSS
    assert ".hero__actions .btn { height: 44px;" in CSS
    assert ".hero__actions .btn { height: 40px" not in CSS


def test_landscape_shows_the_scroll_cue():
    land = block("@media (max-width: 1000px) and (max-height: 500px) {")
    assert ".hero__cue { display: none; }" not in land
    assert ".hero__cue { left: max(var(--pad)" in land


def test_iframe_sandbox_has_only_valid_tokens():
    assert 'const SANDBOX = "allow-scripts allow-same-origin";' in APP
    assert "allow-presentation" not in APP


HERO = (ROOT / "static/js/hero.js").read_text(encoding="utf-8")


def test_band_always_has_a_backdrop_image_under_the_video():
    # every slide carries a 16:9 YouTube still as its CSS background, under the poster <img> and the iframe
    assert 's.style.backgroundImage = `url("${thumb(t.id, "mqdefault")}")`;' in HERO
    assert ".slide { background-color: #000; background-position: center; background-size: cover;" in CSS
    assert "https://i.ytimg.com" in (ROOT / "app.py").read_text(encoding="utf-8")  # img-src allows the still


def test_video_fades_in_only_when_it_is_really_moving():
    assert "if (now - t0 < REVEAL_ADVANCE_S) { if (++checks < REVEAL_TRIES) entry.reveal = setTimeout(reveal, REVEAL_POLL_MS); return; }" in HERO
    assert ".slide__video { position: absolute; inset: 0; overflow: hidden; opacity: 0;" in CSS
    assert ".slide__video.is-playing { opacity: 1; }" in CSS


def test_band_iframe_is_scaled_to_cover():
    b = block(BAND)
    assert ".slide__video iframe { transform: translate(-50%,-50%) scale(1.3); }" in b
