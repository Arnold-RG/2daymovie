"""Live trailer background: autoplays muted on first visit, full display height by default."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
HERO = (ROOT / "static/js/hero.js").read_text(encoding="utf-8")
CSS = (ROOT / "static/css/app.css").read_text(encoding="utf-8")


def test_no_click_to_load_gate_remains():
    for js in (APP, HERO):
        for gone in ("yt_consent", "ytConsent", "grantYTConsent", "heroConsent", "is-gated", "\"Play trailer\""):
            assert gone not in js, gone
    assert "consent-note" not in CSS and "modal__gate" not in CSS


def test_hero_starts_live_muted_trailers_on_load():
    build = HERO.split("function build() {", 1)[1].split("function paint()", 1)[0]
    assert "if (reduceMotion.matches) return;" in build, "reduced motion keeps the static poster"
    after_rm = build.split("if (reduceMotion.matches) return;", 1)[1]
    assert re.search(r"loadYT\(\)\.then\(\(YT\) => \{ YTlib = YT; warm\(\); \}\)", after_rm), "player loads right away"
    assert "autoplay: 0, mute: 1" in HERO and "playsinline: 1" in HERO  # autoplay=1 makes YouTube draw its own pause glyph
    assert "e.target.mute(); // start silent" in HERO and "e.target.playVideo()" in HERO


def test_loadyt_has_no_gate():
    body = APP.split("function loadYT() {", 1)[1].split("\n  }\n", 1)[0]
    assert "reject(new Error(\"YouTube not loaded" not in body
    assert body.strip().startswith("if (ytReady) return ytReady;")


def test_full_display_height_is_the_default(client):
    html = client.get("/").get_data(as_text=True)
    assert re.search(r'<section class="hero" id="top" data-size="full"', html)
    assert 'const STORE_KEY = "tdm.hero.v2"' in HERO, "storage key bumped so old saved sizes are ignored"
    assert HERO.count(': "full";') == 2, "default and fallback size are Full"
    full = re.search(r'\.hero\[data-size="full"\] \{([^}]*)\}', CSS).group(1)
    assert "height: 100vh" in full and "height: 100svh" in full


def test_video_covers_the_hero_without_letterboxing():
    assert ".slide__video { container-type: size; }" in CSS
    assert "width: max(100cqw, 177.78cqh); height: max(100cqh, 56.25cqw);" in CSS
    assert "translate(-50%,-50%) scale(1.18)" in CSS


def test_privacy_note_says_trailers_autoplay(client):
    html = client.get("/").get_data(as_text=True)
    priv = html.split('id="privacy"', 1)[1].split("</section>", 1)[0]
    assert "play automatically, muted" in priv and "YouTube may set its own cookies" in priv
    assert "click-to-load" not in priv and "yt_consent" not in priv


def test_screen_reader_text_in_cards_cannot_widen_the_page():
    # .sr is position:absolute; cards must contain it or it escapes the row scroller
    # and widens the mobile layout viewport (seen as a zoomed-out page on phones).
    assert re.search(r"^\.card \{ position: relative;", CSS, re.M)


def test_video_revealed_only_after_youtube_overlay_autohides():
    # YouTube shows its own centre play/pause button for ~4 s after each play, even with controls:0.
    assert "const REVEAL_MS = 4300" in HERO
    assert "setTimeout(() => {" in HERO and "}, REVEAL_MS);" in HERO
    assert "clearTimeout(p.reveal)" in HERO and "clearTimeout(entry.reveal)" in HERO
