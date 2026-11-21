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
    assert "autoplay: i === cur ? 1 : 0, mute: 1" in HERO and "playsinline: 1" in HERO  # iOS: muted inline autoplay; the poster hides YouTube's button
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


def test_stalled_autoplay_is_retried_then_waits_for_a_tap():
    # WebKit/Safari can ignore the first muted playVideo(); keep asking, then fall back to a tap.
    assert "const KICK_MS = 1200, KICK_TRIES = 10" in HERO
    assert "if (entry.wantPlay && !holds.size) kick(entry);" in HERO
    assert "p.player.mute(); p.player.playVideo();" in HERO
    for g in ('"pointerdown"', '"touchstart"', '"keydown"', '"scroll"'):
        assert g in HERO
    assert 'heroEl.classList.add("is-blocked")' in HERO and "tapThrough()" in HERO
    assert ".slide__video.is-tappable { pointer-events: auto; }" in CSS


def test_assets_are_cache_busted_per_build():
    from app import app, asset_version
    v = asset_version()
    assert len(v) == 10
    html = app.test_client().get("/").get_data(as_text=True)
    for a in ("static/css/app.css", "static/js/hero.js", "static/js/app.js", "static/js/search.js"):
        assert f"{a}?v={v}" in html
    exported = (ROOT / "index.html").read_text(encoding="utf-8")
    assert f"static/js/hero.js?v={v}" in exported  # export_site.py was re-run after the last JS/CSS edit
