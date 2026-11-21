"""Page titles, descriptions, section/genre landing pages, sitemap and robots.txt.

The site is one app shell; each landing page (/explore/<slug>/) is the same
shell with its own title, description and canonical URL, opening at its
section or genre row. Shared by app.py (live) and scripts/export_site.py.
"""
from __future__ import annotations

import os
import re
from collections import Counter
from xml.sax.saxutils import escape

# Canonical public site (Render static site serving the repo root).
SITE_URL = os.getenv("SITE_URL", "https://twodaymovie-site.onrender.com/").rstrip("/") + "/"
PAGES_URL = "https://arnold-rg.github.io/2daymovie/"
BRAND = "2DayMovie"

# Must match SECTIONS / GENRES / GENRE_MIN in static/js/app.js.
SECTIONS = [
    ("trailers", "trailers", "Upcoming Movie Trailers 2026",
     "Watch official trailers for the biggest upcoming 2026 films, including Avengers: Doomsday, with release dates and countdowns."),
    ("movies", "movies", "Watch Full Movies Free: Nollywood, Bollywood, Asian and French Films",
     "Stream full-length movies free through official YouTube embeds: Nollywood, Bollywood, Asian cinema, French films, Kinyarwanda movies and more."),
    ("series", "series", "Watch TV Series and Drama Episodes Free",
     "Binge full TV series episodes free on 2DayMovie: Nollywood series, Rwandan series, anime, Asian dramas and more, all from official YouTube channels."),
    ("kids", "kids", "Kids' Shows and Full Episodes for Children",
     "Made-for-kids full episodes of preschool favourites and children's shows, played free through official YouTube embeds."),
    ("cartoons", "cartoons", "Cartoons and Animated Episodes",
     "Watch full cartoon episodes and animated shows for all ages, free through official YouTube embeds."),
    ("ai", "ai", "AI Animation and Manhwa Recaps",
     "Long-form AI animation and manhwa story recaps, collected in one place to watch free on 2DayMovie."),
    ("wildlife", "wildlife", "Wildlife, Nature and Travel Documentaries",
     "Wildlife and nature documentaries plus travel and adventure films, many in 4K: animals, oceans and amazing places on Earth, free to stream."),
    ("genres", "genres", "Browse Movies and Series by Genre",
     "Find something to watch by genre: drama, action, adventure, sci-fi, musical, horror, comedy, romance, thriller and documentary."),
]
GENRES = ["Drama", "Action", "Adventure", "Sci-Fi", "Musical", "Horror", "Comedy", "Romance", "Thriller", "Documentary"]
GENRE_MIN = 6

HOME = {
    "slug": "", "anchor": "",
    "title": "2DayMovie: Watch Free Movies, TV Series, Kids' Shows and Upcoming Trailers",
    "description": ("Stream full movies, TV series, kids' shows, cartoons and nature documentaries free through official "
                    "YouTube embeds, plus trailers for the biggest upcoming films."),
}


def genre_slug(g: str) -> str:
    return "genre-" + re.sub(r"[^a-z0-9]+", "-", g.lower())


def genre_counts(catalog: dict) -> Counter:
    items = catalog if isinstance(catalog, list) else catalog.get("items", [])
    c: Counter = Counter()
    for it in items:
        gs = it.get("genres") or []
        for g in set(gs[1:]):
            c[g] += 1
    return c


def pages(catalog: dict) -> list[dict]:
    """Every public page: home, sections, then genres that have a row on the site."""
    out = [dict(HOME)]
    for slug, anchor, title, desc in SECTIONS:
        out.append({"slug": slug, "anchor": anchor, "title": f"{title} | {BRAND}", "description": desc})
    counts = genre_counts(catalog)
    for g in GENRES:
        if counts[g] >= GENRE_MIN:
            s = genre_slug(g)
            out.append({
                "slug": s, "anchor": s,
                "title": f"Watch {g} Movies and Series Free | {BRAND}",
                "description": f"{counts[g]} {g.lower()} movies and series to stream free on {BRAND}, all through official YouTube embeds.",
            })
    return out


def explore_links(catalog: dict) -> list[dict]:
    """Every /explore/<slug>/ page with a short label, for the /explore/ index."""
    out = []
    for p in pages(catalog)[1:]:
        label = p["title"].split(" | ")[0]
        if label.startswith("Watch ") and label.endswith(" Movies and Series Free"):
            label = label[len("Watch "):-len(" Movies and Series Free")]
        out.append({"slug": p["slug"], "label": label})
    return out


def page_path(p: dict) -> str:
    return f"explore/{p['slug']}/" if p["slug"] else ""


def sitemap_xml(catalog: dict, site_url: str = SITE_URL) -> str:
    lastmod = str((catalog.get("generated") if isinstance(catalog, dict) else "") or "")[:10]
    rows = []
    for p in pages(catalog):
        loc = escape(site_url + page_path(p))
        lm = f"<lastmod>{lastmod}</lastmod>" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", lastmod) else ""
        prio = "1.0" if not p["slug"] else ("0.6" if p["slug"].startswith("genre-") else "0.8")
        rows.append(f"  <url><loc>{loc}</loc>{lm}<changefreq>daily</changefreq><priority>{prio}</priority></url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n")


AI_AND_SEARCH_BOTS = ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "Bingbot", "Googlebot"]
PRIVATE_PATHS = ["/metrics", "/healthz", "/readyz"]


def robots_txt(site_url: str = SITE_URL) -> str:
    rules = "Allow: /\n" + "".join(f"Disallow: {p}\n" for p in PRIVATE_PATHS)
    named = "".join(f"User-agent: {b}\n" for b in AI_AND_SEARCH_BOTS)
    return ("# 2DayMovie: a public catalog of YouTube embeds. Search engines and AI crawlers are welcome.\n"
            "User-agent: *\n" + rules + "\n"
            "# Named explicitly so no crawler-specific default blocks them.\n" + named + rules + "\n"
            f"Sitemap: {site_url}sitemap.xml\n")
