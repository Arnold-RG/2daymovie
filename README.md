# 2daymovie.to

Legal movie discovery platform — browse a large catalog, watch **official full trailers**, and open **licensed streaming guides**. No accounts. We do **not** host or stream full copyrighted films.

**Official live site:** https://twodaymovie.onrender.com/

## Features

- Home rows: trending, popular, now playing, top rated
- Full catalog browse with pagination and sorting
- Search and genre browse
- Movie pages with synopsis, cast, similar titles, official full trailer, and licensed “where to watch”
- No login required

## Quick start

```bash
cd 2daymovie
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open [http://localhost:5000](http://localhost:5000).

### Full live catalog (TMDB)

Set `TMDB_API_KEY` in Render Environment (or local `.env`) to unlock the full TMDB catalog with pagination. Free key: https://www.themoviedb.org/settings/api

## Deploy

Render auto-deploys from `main`. Live URL: https://twodaymovie.onrender.com/

GitHub Pages mirror: https://arnold-rg.github.io/2daymovie/

## Tests

```bash
pytest
```

## Legal note

Official full trailers come from YouTube via TMDB. “Where to watch” opens TMDB’s legal watch guide for licensed services. Pirate streaming indexes are not supported.
