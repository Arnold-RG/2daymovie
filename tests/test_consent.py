"""Click-to-load YouTube: no player or API request until the visitor asks for video."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "static/js/app.js").read_text(encoding="utf-8")
HERO = (ROOT / "static/js/hero.js").read_text(encoding="utf-8")
CSS = (ROOT / "static/css/app.css").read_text(encoding="utf-8")


def test_page_makes_no_youtube_connection_before_consent(client):
    html = client.get("/").get_data(as_text=True)
    tags = re.findall(r"<(?:link|script|iframe|img)\b[^>]*>", html)
    assert not [t for t in tags if "youtube.com" in t or "youtube-nocookie.com" in t], \
        "no preconnect, preload, script or frame to YouTube before consent"
    assert not re.search(r"<iframe", html), "no iframe in the server HTML"
    assert "iframe_api" not in html


def test_load_yt_refuses_without_consent():
    body = APP.split("function loadYT() {", 1)[1].split("\n  }\n", 1)[0]
    first = body.strip().splitlines()[0]
    assert "ytConsent()" in first and "reject" in first, "loadYT must bail out first when there is no consent"
    assert 'CONSENT_KEY = "yt_consent"' in APP
    assert 'localStorage.setItem(CONSENT_KEY, "1")' in APP
    assert 'new CustomEvent("tdm:yt-consent")' in APP


def test_only_user_actions_grant_consent():
    assert "function openPlayer(id, userAction = true)" in APP
    assert "if (userAction) grantYTConsent();" in APP
    assert "openPlayer(v, false)" in APP, "a shared ?v= link must not auto-load YouTube"
    gate = APP.split("if (!ytConsent()) {", 1)[1].split("return;", 1)[0]
    assert "Play video" in gate and "embedFrame" not in gate


def test_every_embed_path_is_behind_consent():
    # hero: the player is only built from startVideo(), which runs on consent
    assert "if (TDM.ytConsent()) startVideo();" in HERO
    assert 'addEventListener("tdm:yt-consent", onConsent' in HERO
    assert HERO.count("loadYT()") == 1 and "function startVideo()" in HERO
    # modal: embedFrame comes after the consent gate's return
    open_player = APP.split("function openPlayer(", 1)[1].split("function closePlayer", 1)[0]
    assert open_player.index("if (!ytConsent())") < open_player.index("embedFrame(")


def test_hero_gate_button_and_note():
    assert 'play.id = "heroConsent"' in HERO and '"Play trailer"' in HERO
    assert '"Video by YouTube, loads YouTube cookies"' in HERO
    assert 'setAttribute("aria-describedby", "heroConsentNote")' in HERO
    assert ".hero.is-gated .hero__soundgroup" in CSS, "no sound switch before there is a video"
    assert ".hero.is-gated .hero__playpause" not in CSS, "posters still auto-advance, so Pause stays (WCAG 2.2.2)"


def test_privacy_note_describes_click_to_load(client):
    html = client.get("/").get_data(as_text=True)
    priv = html.split('id="privacy"', 1)[1].split("</section>", 1)[0]
    for phrase in ("click-to-load", "Play trailer", "yt_consent", "i.ytimg.com", "YouTube still sets its own cookies"):
        assert phrase in priv, phrase
