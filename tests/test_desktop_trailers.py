"""Desktop trailers: reduced motion still plays, unplayable trailers are skipped (Ateck, 21 Nov)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERO = (ROOT / "static/js/hero.js").read_text(encoding="utf-8")


def test_reduced_motion_does_not_disable_the_players():
    for gone in ("players.has(i) || reduceMotion.matches", "if (!YTlib || reduceMotion.matches) return;",
                 "ui.pause.hidden = true", "ui.soundGroup.hidden = true"):
        assert gone not in HERO, gone
    # still no auto-advance and no slide motion under reduced motion
    assert "if (reduceMotion.matches) return; // no auto-advance" in HERO
    assert "const fade = reduceMotion.matches;" in HERO
    # a pause under reduced motion is remembered and honoured on the next visit
    assert 'if (reduceMotion.matches) prefs.save({ still: holds.has("user") });' in HERO
    assert 'if (reduceMotion.matches && saved.still === true) pause("user");' in HERO


def test_unplayable_trailer_is_skipped():
    err = HERO.split("onError: (e) => {", 1)[1].split("},\n", 1)[0]
    assert "deadIds.add(t.id)" in err and "skipDead(1)" in err
    assert "const SKIP_MS = 1500" in HERO
    assert "if (left <= 0) { skipDead(1); return; }" in HERO


def test_dead_trailers_are_remembered_outside_the_players():
    assert "const deadIds = new Set();" in HERO and "deadIds.add(t.id)" in HERO
    assert "entry.dead" not in HERO and "p.dead" not in HERO
    skip = HERO.split("function skipDead(dir) {", 1)[1].split("\n    }\n", 1)[0]
    assert "if (!deadIds.has(trailers[j].id)) { go(j, dir, false); return; }" in skip
    assert "allDead = true;" in skip and 'pause("user");' in skip
    # the skip timeout is stored and cleared by go() and pauseAt()
    assert "skipTimer = setTimeout(" in HERO
    go = HERO.split("function go(target, dir, manual) {", 1)[1].split("\n    }\n", 1)[0]
    pa = HERO.split("function pauseAt(i) {", 1)[1].split("\n    }\n", 1)[0]
    assert "clearTimeout(skipTimer);" in go and "if (skipFor === i) clearTimeout(skipTimer);" in pa
    assert "if (allDead) retryAll();" in HERO


def test_youtube_centre_button_is_veiled_not_waited_for():
    css = (ROOT / "static/css/app.css").read_text(encoding="utf-8")
    assert "const VEIL_MS = 4000" in HERO and 'box.classList.add("is-veiled")' in HERO
    assert ".slide__video.is-veiled::after { opacity: 1;" in css and "backdrop-filter: blur(14px)" in css


def test_quick_pause_and_mute_follow_the_skip_link(client):
    html = client.get("/").get_data(as_text=True)
    body = html.split("<body>", 1)[1]
    skip = body.index('class="skip" href="#main"')
    assert skip < body.index('id="quickPause"') < body.index('id="quickMute"') < body.index('<header class="nav"')
