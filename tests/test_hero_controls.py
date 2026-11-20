"""Hero control bar: presence, labels and ARIA state of every control.

The bar is server-rendered in templates/index.html so these checks run on
the HTML Flask serves and on the exported static pages (Render + Pages).
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HERO_JS = (ROOT / "static/js/hero.js").read_text(encoding="utf-8")
CSS = (ROOT / "static/css/app.css").read_text(encoding="utf-8")


class Tree(HTMLParser):
    """Flat list of start tags with attrs, parent ids, and text per element id."""

    VOID = {"input", "img", "br", "meta", "link", "path", "hr", "source"}

    def __init__(self):
        super().__init__()
        self.nodes, self.stack, self.text = [], [], {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        node = {"tag": tag, "attrs": a, "ancestors": [n["attrs"].get("id") for n in self.stack if n["attrs"].get("id")]}
        self.nodes.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1]["tag"] == tag and tag not in self.VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        for n in self.stack:
            key = n["attrs"].get("id") or id(n)
            self.text[key] = self.text.get(key, "") + data
        if self.stack:
            self.stack[-1].setdefault("own", "")
            self.stack[-1]["own"] += data

    def by_id(self, i):
        found = [n for n in self.nodes if n["attrs"].get("id") == i]
        assert len(found) == 1, f"expected exactly one #{i}"
        return found[0]

    def inside(self, i):
        return [n for n in self.nodes if i in n["ancestors"]]


def parse(html: str) -> Tree:
    t = Tree()
    t.feed(html)
    return t


def pages(client):
    yield "flask", client.get("/").get_data(as_text=True)
    for rel in ("index.html", "docs/index.html"):
        p = ROOT / rel
        if p.exists():
            yield rel, p.read_text(encoding="utf-8")


@pytest.fixture()
def tree(client):
    return parse(client.get("/").get_data(as_text=True))


def test_control_bar_is_a_labelled_toolbar_inside_the_hero(tree):
    bar = tree.by_id("heroBar")
    assert bar["attrs"].get("role") == "toolbar"
    assert bar["attrs"].get("aria-label")
    assert bar["attrs"].get("aria-controls") == "heroTrack"
    assert "top" in bar["ancestors"], "control bar must live inside the hero section"
    hero = tree.by_id("top")
    assert hero["attrs"].get("data-size") == "full", "Full display height is the default"


@pytest.mark.parametrize("bid,pressed,label,keys", [
    ("heroPause", "false", "Pause trailers", "Space K"),
    ("heroMute", "false", "Unmute trailer", "M"),          # muted by default
    ("heroFullscreen", "false", "Enter fullscreen", "F"),
])
def test_toggle_buttons_have_state_label_and_shortcut(tree, bid, pressed, label, keys):
    b = tree.by_id(bid)
    a = b["attrs"]
    assert b["tag"] == "button" and a.get("type") == "button"
    assert a.get("aria-pressed") == pressed
    assert a.get("aria-label") == label
    assert a.get("aria-keyshortcuts") == keys
    first_key = keys.split()[0]
    assert first_key in a.get("data-tip", ""), "tooltip must show the keyboard shortcut"


def test_every_control_has_an_accessible_name_and_is_a_real_button(tree):
    for n in tree.inside("heroBar"):
        if n["tag"] == "button":
            a = n["attrs"]
            assert a.get("type") == "button"
            assert a.get("aria-label") or (n.get("own") or "").strip(), "button without a name"
            assert a.get("data-tip"), "every bar button gets a tooltip"
        if n["tag"] == "svg":
            assert n["attrs"].get("aria-hidden") == "true"


def test_sliders_are_labelled_ranges(client, tree):
    html = client.get("/").get_data(as_text=True)
    for rid, lo, hi in (("heroVolume", "0", "100"), ("heroBrightness", "0.4", "1.6")):
        r = tree.by_id(rid)["attrs"]
        assert r.get("type") == "range" and r.get("min") == lo and r.get("max") == hi
        assert r.get("aria-valuetext")
        assert re.search(rf'<label[^>]+for="{rid}"[^>]*>[^<]+</label>', html), f"#{rid} needs a label"


@pytest.mark.parametrize("group,values,checked,attr", [
    ("heroBrightPresets", ["dim", "normal", "bright"], "normal", "data-level"),
    ("heroSizes", ["compact", "standard", "full"], "full", "data-size"),
])
def test_segmented_controls_are_radiogroups(tree, group, values, checked, attr):
    g = tree.by_id(group)
    assert g["attrs"].get("role") == "radiogroup" and g["attrs"].get("aria-label")
    radios = [n for n in tree.inside(group) if n["attrs"].get("role") == "radio"]
    assert [r["attrs"][attr] for r in radios] == values
    on = [r for r in radios if r["attrs"].get("aria-checked") == "true"]
    assert len(on) == 1 and on[0]["attrs"][attr] == checked
    # roving tabindex: exactly one tab stop, on the checked radio
    assert [r["attrs"].get("tabindex") for r in radios].count("0") == 1
    assert on[0]["attrs"].get("tabindex") == "0"
    for r in radios:
        assert (r.get("own") or "").strip(), "radio needs a visible label"


def test_cycle_buttons_for_the_compact_bar(tree):
    for bid, keys in (("heroBrightCycle", "B"), ("heroSizeCycle", None)):
        a = tree.by_id(bid)["attrs"]
        assert a.get("aria-label")
        if keys:
            assert a.get("aria-keyshortcuts") == keys


def test_exported_pages_ship_the_same_control_bar(client):
    ids = ("heroBar", "heroPause", "heroMute", "heroVolume", "heroBrightPresets", "heroBrightness",
           "heroSizes", "heroFullscreen", "heroBrightCycle", "heroSizeCycle")
    for name, html in pages(client):
        t = parse(html)
        for i in ids:
            t.by_id(i)
        assert 'style="' not in html.split('id="heroBar"', 1)[1].split("</section>", 1)[0], name


def test_hero_js_drives_youtube_api_and_remembers_choices():
    for call in (".mute()", ".unMute()", ".setVolume(", ".isMuted()", "requestFullscreen", "fullscreenchange",
                 "localStorage", "visibilitychange"):
        assert call in HERO_JS, call
    for key in ('"m"', '"b"', '"f"', '"k"', '" "'):
        assert key in HERO_JS, f"shortcut {key}"
    assert "innerHTML" not in HERO_JS and "insertAdjacentHTML" not in HERO_JS
    # hero iframe keeps YouTube chrome hidden and stays sandboxed
    for p in ("controls: 0", "disablekb: 1", "pointerEvents", "TDM.SANDBOX"):
        assert p in HERO_JS


def test_css_covers_sizes_brightness_and_reduced_motion():
    for sel in ('.hero[data-size="compact"]', '.hero[data-size="standard"]', '.hero[data-size="full"]', ":fullscreen"):
        assert sel in CSS
    assert "brightness(var(--hero-brightness" in CSS and "transition: filter" in CSS
    assert "@keyframes kenburns" in CSS and "@keyframes logoIn" in CSS
    rm = CSS.split("@media (prefers-reduced-motion: reduce)", 1)[1]
    for sel in (".hero.is-ready", "slide__poster", ".hero__logo"):
        assert sel in rm, f"reduced motion must disable {sel}"
