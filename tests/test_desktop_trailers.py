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
    assert "const VEIL_MS = 4000" in HERO and 'box.classList.add("is-veiled")' in HERO and "veil(box);" in HERO
    assert ".slide__video.is-veiled::after { opacity: 1;" in css and "backdrop-filter: blur(14px)" in css


def test_quick_pause_and_mute_follow_the_skip_link(client):
    html = client.get("/").get_data(as_text=True)
    body = html.split("<body>", 1)[1]
    skip = body.index('class="skip" href="#main"')
    assert skip < body.index('<header class="nav"') < body.index('id="quickPause"') < body.index('id="quickMute"') < body.index('class="nav__inner"')


def test_parking_cancels_background_timers():
    pause = HERO.split("function pause(reason) {", 1)[1].split("\n    }\n", 1)[0]
    assert "clearTimeout(neighbourTimer);" in pause and "clearTimeout(skipTimer);" in pause
    resume = HERO.split("function resume(reason) {", 1)[1].split("\n    }\n", 1)[0]
    assert "neighbourTimer = setTimeout(warmNeighbours, NEIGHBOUR_MS)" in resume


def test_veil_is_one_removable_block():
    css = (ROOT / "static/css/app.css").read_text(encoding="utf-8")
    js = HERO.split("/* ---------- centre veil", 1)[1].split("/* ---------- end centre veil ---------- */", 1)[0]
    assert "const VEIL_MS = 4000" in js and "function veil(box)" in js
    assert HERO.count("veil(box)") == 2  # the definition and its single call
    assert HERO.count("is-veiled") == 2 and "VEIL_MS" not in HERO.replace(js, "")
    block = css.split("/* ---- centre veil", 1)[1].split("/* ---- end centre veil ---- */", 1)[0]
    assert "slide__video::after" not in css.replace(block, "")


def test_in_hero_pause_and_mute_are_not_tab_stops(client):
    html = client.get("/").get_data(as_text=True)
    assert 'id="heroPause" type="button" tabindex="-1"' in html
    assert 'id="heroMute" type="button" tabindex="-1"' in html
    assert "skip-media" not in html and 'role="group" aria-label="Background trailers"' not in html
    header = html.split('<header class="nav" id="nav">', 1)[1].split("</header>", 1)[0]
    assert 'id="quickPause"' in header and 'id="quickMute"' in header
