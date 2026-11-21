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
    assert "entry.dead = true" in err and "skipDead(1)" in err
    assert "const SKIP_MS = 1500" in HERO
    assert "if (left <= 0) { skipDead(1); return; }" in HERO
    assert "if (!p || !p.dead) { go(j, dir, false); return; }" in HERO
