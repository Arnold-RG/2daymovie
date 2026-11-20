#!/usr/bin/env python3
"""Render the app shell to static files.

    python scripts/export_site.py            # writes ./index.html, ./404.html and docs/
    python scripts/export_site.py --out DIR  # writes a self-contained copy to DIR

The repo root is what the Render static site publishes, and docs/ is what GitHub
Pages serves, so both are regenerated from templates/ here.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import CSP_META, app  # noqa: E402

DATA = ["catalog.json", "trailers.json"]


def render(name: str, **ctx) -> str:
    with app.test_request_context("/"):
        from flask import render_template
        return render_template(name, **ctx)


PAGES_BASE = "/2daymovie/"  # GitHub Pages project path for docs/


def write_pages(target: Path, error_base: str = "/") -> None:
    """index.html uses relative URLs; 404.html needs an absolute base because it
    is served at whatever nested path was not found."""
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text(render("index.html", base="", csp_meta=CSP_META), encoding="utf-8")
    (target / "404.html").write_text(render("404.html", base=error_base), encoding="utf-8")


def export(out: Path, error_base: str = "/") -> None:
    if out.exists():
        shutil.rmtree(out)
    write_pages(out, error_base)
    shutil.copytree(ROOT / "static", out / "static")
    (out / "data").mkdir()
    for f in DATA:
        shutil.copy2(ROOT / "data" / f, out / "data" / f)
    shutil.copy2(ROOT / "robots.txt", out / "robots.txt")
    (out / ".nojekyll").write_text("")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--base", default="/", help="absolute base for 404.html in --out")
    args = ap.parse_args()
    if args.out:
        export(Path(args.out).resolve(), args.base)
    else:
        write_pages(ROOT)
        export(ROOT / "docs", PAGES_BASE)
