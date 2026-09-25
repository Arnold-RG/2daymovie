# 2daymovie.to

Legal movie discovery platform — browse a large catalog, watch **official trailers**, and open **licensed streaming links**. No accounts. We do **not** host or stream full copyrighted films.

## Features

- Home rows: trending, popular, now playing, top rated
- Full catalog browse with pagination and sorting
- Search and genre browse
- Movie pages with synopsis, cast, similar titles, trailer, and legal “where to watch” providers
- Works offline with a demo catalog; switch to live TMDB for the full catalog
- No login required

## Quick start

```bash
cd 2daymovie
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Open [http://localhost:5000](http://localhost:5000).

### Full catalog (TMDB)

1. Create a free API key: [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)
2. Copy `.env.example` → `.env` and set `TMDB_API_KEY`
3. Restart the app

Optional: set `TMDB_WATCH_REGION` (default `US`) for regional provider results.

## Deploy (permanent live URL)

**Live now (GitHub Pages):** https://arnold-rg.github.io/2daymovie/

Paste a free TMDB API key in the site header to unlock the full catalog.

### Render (optional Flask hosting)

1. Open: https://render.com/deploy?repo=https://github.com/Arnold-RG/2daymovie
2. Sign in with GitHub and click **Apply** / **Deploy**
3. Optional: set `TMDB_API_KEY` in Render → Environment
4. Every push to `main` redeploys automatically

### Docker

```bash
docker build -t 2daymovie .
docker run -d -p 5000:5000 --env-file .env --name 2daymovie 2daymovie
```

## Tests

```bash
pytest
```

## Stack

- Python / Flask
- TMDB API (metadata, posters, trailers, watch providers)
- HTML / CSS / JS

## Legal note

`2daymovie.to` is a discovery UI. Trailers are embedded from YouTube when available via TMDB. Watch links point to licensed services (via TMDB / JustWatch). Do not use this project to host or redistribute copyrighted media.
