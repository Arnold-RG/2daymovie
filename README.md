# 2daymovie.to

Legal movie discovery — curated **2000–2026** library, **official full trailers**, and **licensed HD streaming guides**. No accounts. We do **not** host copyrighted films.

**Official live site:** https://twodaymovie.onrender.com/

## Features

- Library timeline for every year from 2000 → 2026
- Year pages with poster grids and “Watch room”
- Watch room: official full YouTube trailer + TMDB legal HD stream guide
- Search / browse / genres via TMDB when `TMDB_API_KEY` is set
- No login required

## Routes

- `/library` — year timeline
- `/year/2010` — that year’s curated list
- `/watch/<id>` — immersive trailer + legal stream CTA
- `/movie/<id>` — full details

## Quick start

```bash
cd 2daymovie
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Rebuild metadata cache (optional):

```bash
python -u scripts/resolve_year_catalog.py
```

## Deploy

Render auto-deploys from `main`: https://twodaymovie.onrender.com/

## Legal note

Trailers are official YouTube embeds via TMDB. “Stream in HD” opens TMDB’s licensed-provider guide. Pirate streaming sites are not supported.
