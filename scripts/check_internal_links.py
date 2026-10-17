"""Fail when docs/ contains an internal link GitHub Pages cannot resolve.

Pages publishes this project under a repository subpath (BASE_PATH, usually
/2daymovie). A root-relative URL such as /watch/621304 is requested from the
domain root and 404s, even when docs/watch/621304/index.html exists. Links that
stay inside the base path must also point at a file the export wrote.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
NAV_KINDS = {"href", "data-href", "action"}
ASSET_RELS = {
    "stylesheet",
    "icon",
    "shortcut",
    "apple-touch-icon",
    "preload",
    "modulepreload",
}
SKIP_PREFIXES = ("#", "mailto:", "tel:", "javascript:", "data:")
CSS_URL = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""", re.I)
SITEMAP_LOC = re.compile(r"<loc>\s*([^<]+?)\s*</loc>", re.I)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[tuple[str, str]] = []
        self._json = False
        self._json_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        if attr.get("data-href"):
            self.refs.append(("data-href", attr["data-href"]))
        if tag == "a" and attr.get("href"):
            self.refs.append(("href", attr["href"]))
        if tag == "form" and attr.get("action"):
            self.refs.append(("action", attr["action"]))
        if tag in {"img", "script", "source", "video", "audio"} and attr.get("src"):
            self.refs.append(("src", attr["src"]))
        if tag == "link" and attr.get("href"):
            rels = set(attr.get("rel", "").lower().split())
            if rels & ASSET_RELS:
                self.refs.append(("asset", attr["href"]))
        style = attr.get("style") or ""
        for match in CSS_URL.findall(style):
            self.refs.append(("style", match))
        if tag == "script" and attr.get("id") == "search-index":
            self._json = True
            self._json_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag != "script" or not self._json:
            return
        self._json = False
        raw = "".join(self._json_parts).strip()
        if not raw:
            return
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self.refs.append(("search-index", ""))
            return
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict) and item.get("href"):
                    self.refs.append(("href", str(item["href"])))

    def handle_data(self, data: str) -> None:
        if self._json:
            self._json_parts.append(data)


def normalize_base(base: str | None) -> str:
    raw = (base or "").strip().rstrip("/")
    if raw and not raw.startswith("/"):
        raw = "/" + raw
    return raw


def infer_base(root: Path) -> str:
    index = root / "index.html"
    if not index.is_file():
        return ""
    text = index.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"""(?:href|src)\s*=\s*["'](/[^"']+?)/static/""", text)
    if not match:
        return ""
    return match.group(1).rstrip("/")


def html_refs(text: str) -> list[tuple[str, str]]:
    parser = _LinkParser()
    parser.feed(text)
    parser.close()
    return parser.refs


def _under_base(path: str, base: str) -> bool:
    if not base:
        return path.startswith("/")
    return path == base or path.startswith(base + "/")


def _clean(path: str) -> str:
    if len(path) > 1:
        path = path.rstrip("/")
    return path or "/"


def classify_url(url: str, page_dir: str, base: str) -> tuple[str, str]:
    """Return ('ignore'|'outside'|'check', site path).

    site path includes the Pages base when one is configured.
    """
    raw = (url or "").strip()
    if not raw or raw.startswith(SKIP_PREFIXES) or unquote(raw).startswith("#"):
        return ("ignore", "")
    if raw.startswith("//"):
        return ("ignore", "")
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"}:
        path = _clean(unquote(parsed.path or "/"))
        if _under_base(path, base):
            return ("check", path)
        return ("ignore", "")
    if parsed.scheme:
        return ("ignore", "")
    path = unquote(parsed.path or "")
    if not path:
        return ("ignore", "")
    if path.startswith("/"):
        path = _clean(path)
        if not _under_base(path, base):
            return ("outside", path)
        return ("check", path)
    joined = urlparse(urljoin(page_dir, raw))
    path = _clean(unquote(joined.path or "/"))
    if not _under_base(path, base):
        return ("outside", path)
    return ("check", path)


def page_directory(root: Path, file: Path, base: str) -> str:
    rel = file.relative_to(root).as_posix()
    if rel.endswith("/index.html"):
        folder = rel[: -len("index.html")].rstrip("/")
    else:
        parent = Path(rel).parent.as_posix()
        folder = "" if parent == "." else parent
    prefix = base or ""
    if not folder:
        return f"{prefix}/"
    return f"{prefix}/{folder}/"


def location_site_path(location: str, base: str) -> str | None:
    """Normalize a redirect Location to a site path that includes base."""
    parsed = urlparse(location or "")
    path = _clean(unquote(parsed.path or ""))
    if not path.startswith("/"):
        return None
    prefix = normalize_base(base)
    if prefix and not _under_base(path, prefix):
        path = _clean(prefix + path)
    return path


def to_app_path(site_path: str, base: str) -> str:
    path = site_path or "/"
    if base and (path == base or path.startswith(base + "/")):
        path = path[len(base) :] or "/"
    if not path.startswith("/"):
        path = "/" + path
    return path if path == "/" else path.rstrip("/")


def is_static_asset(app_path: str) -> bool:
    if app_path == "/static" or app_path.startswith("/static/"):
        return True
    suffix = Path(app_path).suffix.lower()
    return suffix in {".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".ico", ".gif", ".xml", ".txt"}


def target_exists(root: Path, site_path: str, base: str) -> bool:
    rel = to_app_path(site_path, base).strip("/")
    if not rel:
        return (root / "index.html").is_file()
    candidate = root.joinpath(*rel.split("/"))
    if candidate.is_file():
        return True
    return (candidate / "index.html").is_file()


def _refs_in_file(path: Path, text: str) -> list[tuple[str, str]]:
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        return html_refs(text)
    refs: list[tuple[str, str]] = []
    if suffix == ".css":
        refs.extend(("style", match) for match in CSS_URL.findall(text))
    elif suffix == ".xml":
        refs.extend(("loc", match.strip()) for match in SITEMAP_LOC.findall(text))
    elif path.name == "robots.txt":
        for line in text.splitlines():
            if line.lower().startswith("sitemap:"):
                refs.append(("sitemap", line.split(None, 1)[1].strip()))
    return refs


def check_site(root: Path, base: str | None = None) -> list[str]:
    root = root.resolve()
    if base is None:
        base = os.getenv("BASE_PATH")
        if base is None:
            base = infer_base(root)
    prefix = normalize_base(base)
    errors: list[str] = []
    if not root.is_dir():
        return [f"{root} is not a directory"]
    files = [path for path in root.rglob("*") if path.is_file()]
    for file in files:
        if file.suffix.lower() not in {".html", ".htm", ".css", ".xml"} and file.name != "robots.txt":
            continue
        text = file.read_text(encoding="utf-8", errors="ignore")
        directory = page_directory(root, file, prefix)
        rel_file = file.relative_to(root).as_posix()
        for kind, url in _refs_in_file(file, text):
            if kind == "search-index" and not url:
                errors.append(f"{rel_file}: search index is not valid JSON")
                continue
            status, site_path = classify_url(url, directory, prefix)
            if status == "ignore":
                continue
            if status == "outside":
                shown = prefix or "/"
                errors.append(
                    f"{rel_file}: {kind} {url!r} is outside the Pages base {shown}"
                )
                continue
            if not target_exists(root, site_path, prefix):
                errors.append(
                    f"{rel_file}: {kind} {url!r} does not match a file ({site_path})"
                )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT / "docs"), help="Exported site directory")
    parser.add_argument(
        "--base",
        default=None,
        help="Pages subpath such as /2daymovie. Defaults to BASE_PATH, then inference.",
    )
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_absolute():
        root = ROOT / root
    errors = check_site(root, args.base)
    if errors:
        limit = 80
        for line in errors[:limit]:
            print(f"BROKEN {line}")
        if len(errors) > limit:
            print(f"... {len(errors) - limit} more")
        print(f"{len(errors)} broken internal link(s) in {root}")
        return 1
    print(f"internal links ok in {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
