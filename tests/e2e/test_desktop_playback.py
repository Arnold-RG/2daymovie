"""Desktop playback on a live-like static export (docs/ served under /2daymovie/, like GitHub Pages).

Real Chromium with its default autoplay policy (no --autoplay-policy flag) and a Windows Edge UA.
Needs Playwright + Chromium and network access to YouTube, so it is skipped unless E2E=1:

    E2E=1 pytest -q tests/e2e
"""
from __future__ import annotations

import functools
import http.server
import os
import re
import socketserver
import tempfile
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.environ.get("E2E") != "1", reason="set E2E=1 (needs Chromium and YouTube)")
EDGE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0")
STATE = """() => { if (!window.TDM || !TDM.hero || !document.querySelector('.slide.is-current')) return { st: null, idx: 0, shown: false, err: null };
  const s = TDM.hero.state(), c = document.querySelector('.slide.is-current');
  return { st: s.playerState, idx: s.index, shown: !!c.querySelector('.slide__video.is-playing'),
           err: c.dataset.ytError || null } }"""


@pytest.fixture(scope="module")
def site():
    tmp = tempfile.mkdtemp()
    os.symlink(ROOT / "docs", Path(tmp) / "2daymovie")
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=tmp)
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/2daymovie/"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()  # default autoplay policy: muted autoplay allowed, unmuted blocked
        yield b
        b.close()


def wait_playing(page, ms):
    """Poll until the current slide reports PLAYING (1) and its poster has faded; return the samples."""
    seen = []
    for _ in range(ms // 250):
        s = page.evaluate(STATE)
        seen.append(s)
        if s["st"] == 1 and s["shown"]:
            return seen
        page.wait_for_timeout(250)
    return seen


@pytest.mark.parametrize("motion", ["no-preference", "reduce"])  # reduce = Windows "Animation effects" off
@pytest.mark.parametrize("size", [(1366, 768), (1920, 1080)])
def test_desktop_trailer_plays_and_poster_fades(site, browser, motion, size):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]}, user_agent=EDGE, reduced_motion=motion)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(site, wait_until="load")
    seen = wait_playing(page, 6_000)  # poster faded to live video within ~6 s of load
    ctx.close()
    assert not errors, errors
    last = seen[-1]
    if last["err"]:  # an unplayable trailer must hand over to the next slide, not sit on its poster
        pytest.fail(f"current trailer errored ({last['err']}) and was not skipped: {seen[-4:]}")
    assert last["st"] == 1, f"player never reached PLAYING: {seen[-4:]}"
    assert last["shown"], f"poster never faded to the live video: {seen[-4:]}"


def test_unplayable_trailer_is_skipped(site, browser):
    """Point the first slide's embed at a video that does not exist: YouTube fires onError, we move on."""
    ctx = browser.new_context(viewport={"width": 1366, "height": 768}, user_agent=EDGE)
    first = re.search(r'hero__ssr-poster" data-id="([\w-]{11})"', (ROOT / "docs/index.html").read_text()).group(1)
    ctx.route(f"**/embed/{first}?*", lambda r: r.continue_(url=r.request.url.replace(first, "AAAAAAAAAAA")))
    page = ctx.new_page()
    page.goto(site, wait_until="load")
    moved = None
    for _ in range(60):
        s = page.evaluate(STATE)
        if s["idx"] != 0:
            moved = s
            break
        page.wait_for_timeout(250)
    assert moved, "the hero stayed on the unplayable first trailer"
    seen = wait_playing(page, 10_000)
    ctx.close()
    assert seen[-1]["st"] == 1 and seen[-1]["shown"], seen[-4:]


def test_all_trailers_broken_stops_after_one_cycle(site, browser):
    """Every embed fails: the hero tries each trailer at most once, then stops on the posters with Play."""
    ctx = browser.new_context(viewport={"width": 1366, "height": 768}, user_agent=EDGE)
    ctx.route(re.compile(r".*/embed/[\w-]{11}\?.*"),
              lambda r: r.continue_(url=re.sub(r"/embed/[\w-]{11}", "/embed/AAAAAAAAAAA", r.request.url)))
    page = ctx.new_page()
    page.goto(site, wait_until="load")
    page.wait_for_function("() => window.TDM && TDM.hero && document.querySelector('.slide')")
    n = page.evaluate("() => document.querySelectorAll('.slide').length")
    moves, last, stopped = 0, 0, None
    for _ in range(480):  # up to 120 s
        s = page.evaluate("""() => ({ idx: TDM.hero.state().index, paused: TDM.hero.state().paused,
            stop: document.querySelector('.hero').classList.contains('is-unplayable'),
            label: document.querySelector('#heroPause').getAttribute('aria-label') })""")
        if s["idx"] != last:
            moves += 1
            last = s["idx"]
        if s["stop"]:
            stopped = s
            break
        page.wait_for_timeout(250)
    assert stopped, f"never stopped after {moves} moves"
    assert moves <= n, f"cycled {moves} times over {n} trailers"
    assert stopped["paused"] and stopped["label"] == "Play trailers"
    idx = stopped["idx"]
    page.wait_for_timeout(4000)  # and it stays put
    assert page.evaluate("() => TDM.hero.state().index") == idx
    assert page.evaluate("() => document.querySelectorAll('.slide__video.is-playing').length") == 0
    ctx.close()


def test_pause_and_mute_are_the_first_tab_stops(site, browser):
    ctx = browser.new_context(viewport={"width": 1366, "height": 768}, user_agent=EDGE)
    page = ctx.new_page()
    page.goto(site, wait_until="load")
    page.wait_for_function("() => window.TDM && TDM.hero && !document.querySelector('#quickPause').hidden")
    order = []
    for _ in range(3):
        page.keyboard.press("Tab")
        order.append(page.evaluate("() => document.activeElement.id || document.activeElement.textContent.trim()"))
    assert order == ["Skip to content", "quickPause", "quickMute"], order
    assert page.evaluate("() => document.activeElement.getBoundingClientRect().left") >= 0  # visible on focus
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Enter")
    assert page.evaluate("() => TDM.hero.state().paused") is True
    assert page.evaluate("() => document.querySelector('#heroPause').getAttribute('aria-pressed')") == "true"
    assert page.evaluate("() => document.querySelector('#quickPause').textContent") == "Play trailers"
    ctx.close()
