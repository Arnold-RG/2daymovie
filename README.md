# 2DayMovie

A Netflix-style streaming site: full movies, series, kids' shows, cartoons, AI animation / manhwa and
nature documentaries, all played through official YouTube embeds, with a header carousel of official
trailers for the biggest upcoming films.

## Layout

| Path | What it is |
| --- | --- |
| `templates/index.html` | App shell (navbar, hero, rows, results grid, player modal) |
| `static/css/app.css` | Dark Netflix-style theme, responsive |
| `static/js/app.js` | Data loading, category rows, navbar, player modal; exposes `window.TDM` |
| `static/js/hero.js` | Header trailer carousel (auto-advance, slide / crossfade, swipe, arrows, dots) |
| `static/js/search.js` | Instant title search |
| `data/catalog.json` | Public catalog: `{ generated, items: [{ id, title, type, genres, duration, thumbnail }] }` |
| `data/trailers.json` | Upcoming trailers: `{ generated, items: [{ title, release_date, youtube_id, start, end }] }` |
| `data/catalog_sources.json` | Internal only (never served by the app): video id to source channel id |
| `scripts/channels.json` | The source channel list, grouped by content type |
| `app.py` | Flask: renders the shell, serves `data/`, `/healthz`, `/readyz`, `/metrics` |

`type` is the section (`movies`, `series`, `kids`, `cartoons`, `ai`, `wildlife`); `genres[0]` is the
row inside that section (for example `Nollywood`, `Rwanda / Kinyarwanda`, `French`, `Asian Dramas`).
Channel names are never shown on the site.

## Run locally

```bash
pip install -r requirements.txt
python app.py            # http://127.0.0.1:8080
pytest -q
```

## Refresh the catalog (no API key)

```bash
pip install -r scripts/requirements.txt   # yt-dlp
python scripts/build_trailers.py          # re-verifies the official upcoming trailers
python scripts/build_catalog.py           # resolves channels, lists uploads, verifies each video embeds
python scripts/export_site.py             # regenerates ./index.html and docs/
```

Every catalog video is checked individually: public, not live, not age-restricted and
`playable_in_embed`. Movies must run 40 minutes or more. Results are cached in `scripts/.cache/`.

## Deploys

- Render static site `twodaymovie-site` publishes the repo root from `main` (`index.html` is generated).
- Render web service `twodaymovie` builds the `Dockerfile` from `main` (gunicorn `app:app`).
- GitHub Pages serves `main:/docs`.
