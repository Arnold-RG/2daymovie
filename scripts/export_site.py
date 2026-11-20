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

import seo  # noqa: E402
from app import CSP_META, _og_image, app, first_trailer_id, load_catalog  # noqa: E402

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
    catalog = load_catalog()
    og = _og_image()
    explore = target / "explore"
    if explore.exists():
        shutil.rmtree(explore)
    for p in seo.pages(catalog):
        rel = seo.page_path(p)
        base = "../../" if rel else ""
        dest = target / rel / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render("index.html", base=base, csp_meta=CSP_META, page=p,
                               canonical=seo.SITE_URL + rel, og_image=og,
                               lcp_id=first_trailer_id()), encoding="utf-8")
    (target / "404.html").write_text(render("404.html", base=error_base), encoding="utf-8")
    # sitemap and robots describe the host that serves this copy
    site = seo.PAGES_URL if error_base == PAGES_BASE else seo.SITE_URL
    (target / "sitemap.xml").write_text(seo.sitemap_xml(catalog, site), encoding="utf-8")
    (target / "robots.txt").write_text(seo.robots_txt(site), encoding="utf-8")


def export(out: Path, error_base: str = "/") -> None:
    if out.exists():
        shutil.rmtree(out)
    write_pages(out, error_base)
    shutil.copytree(ROOT / "static", out / "static")
    (out / "data").mkdir()
    for f in DATA:
        shutil.copy2(ROOT / "data" / f, out / "data" / f)
    (out / ".well-known").mkdir()
    shutil.copy2(ROOT / ".well-known" / "security.txt", out / ".well-known" / "security.txt")
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
