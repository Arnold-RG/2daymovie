"""Every iframe must use youtube-nocookie.com and include a sandbox attribute."""
from __future__ import annotations

import re

from tests.helpers import ROOT, html_routes, iter_text_files, read_text

IFRAME_TAG = re.compile(r"<iframe\b[^>]*>", re.I | re.S)
SRC_ATTR = re.compile(r"""\bsrc\s*=\s*['"]([^'"]+)['"]""", re.I)
SANDBOX_ATTR = re.compile(r"\bsandbox\s*=", re.I)
NOCOOKIE = "youtube-nocookie.com"

# JS that constructs an iframe (template literal or string concat).
JS_IFRAME_EL = re.compile(r"""(?:createElement\(\s*['"]iframe['"]\s*\)|el\(\s*['"]iframe['"]\s*\))""")
JS_IFRAME_SRC = re.compile(
    r"""(?:\.src\s*=\s*|src\s*:)\s*([`'"][^`'"]+[`'"]|[^;\n]+)""",
)
JS_SANDBOX = re.compile(r"""(?:setAttribute\(\s*['"]sandbox['"]|\.sandbox\s*=|sandbox\s*:)""")
JS_NOCOOKIE = re.compile(r"youtube-nocookie\.com")
JS_YT_PLAYER = re.compile(r"YT(?:lib)?\.Player\s*\(")


def test_template_iframes_are_nocookie_and_sandboxed(client, app):
    problems = []
    html_blobs = []
    for path in html_routes(app):
        html_blobs.append((f"GET {path}", client.get(path).get_data(as_text=True)))
    for folder in (ROOT / "templates",):
        for file in iter_text_files(folder):
            html_blobs.append((str(file.relative_to(ROOT)), read_text(file)))
    for label, text in html_blobs:
        for tag in IFRAME_TAG.findall(text):
            src_m = SRC_ATTR.search(tag)
            src = src_m.group(1) if src_m else ""
            if NOCOOKIE not in src:
                problems.append(f"{label}: iframe src is not youtube-nocookie.com")
            if not SANDBOX_ATTR.search(tag):
                problems.append(f"{label}: iframe is missing a sandbox attribute")
    assert not problems, problems


def test_js_created_iframes_use_nocookie_and_sandbox():
    """Fallback iframes and YT.Player mounts in static/js must stay locked down."""
    problems = []
    for file in iter_text_files(ROOT / "static" / "js"):
        text = read_text(file)
        rel = str(file.relative_to(ROOT))
        creates = list(JS_IFRAME_EL.finditer(text))
        players = list(JS_YT_PLAYER.finditer(text))
        if not creates and not players:
            continue
        if creates:
            # Every constructed iframe must be given a nocookie src and a sandbox.
            if not JS_NOCOOKIE.search(text):
                problems.append(f"{rel}: creates an iframe but never mentions youtube-nocookie.com")
            if not JS_SANDBOX.search(text):
                problems.append(
                    f"{rel}: creates an iframe (createElement/el) but never sets a sandbox attribute"
                )
        if players:
            # YT.Player injects an iframe; host must be nocookie and the resulting
            # iframe should get a sandbox attribute (even if set after mount).
            if "NOCOOKIE" not in text and not JS_NOCOOKIE.search(text):
                problems.append(f"{rel}: YT.Player used without a youtube-nocookie host")
            if not JS_SANDBOX.search(text):
                problems.append(
                    f"{rel}: YT.Player is used but the injected iframe is never given a sandbox attribute"
                )
    assert not problems, problems
