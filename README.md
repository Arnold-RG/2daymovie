# 2daymovie

Legal movie discovery — curated **2000–2026** library, **official full trailers embedded on-site**, and **licensed HD streaming guides**. No accounts. We do **not** host copyrighted films.

**2daymovie** is a movie discovery web application created and developed by **Arnold Rurangwa** (Arnold-RG).

- **Website:** https://twodaymovie.onrender.com/
- **GitHub:** https://github.com/Arnold-RG/2daymovie
- **Creator:** Arnold Rurangwa

Once a custom domain is connected, set `OFFICIAL_URL` to `https://2daymovie.com/` (or `.net`) and update this README.

## Features

- Cinema-grade UI: full-bleed heroes, year shelves, immersive Watch rooms
- Categories with honest sort (Top rated / Newest / Oldest / Title)
- Curated **TV series** archive with on-site trailers
- **Upcoming** Oct–Dec 2026 movies and Fall 2026 series
- Search across movies and series (trailer-ready titles only)
- SEO: `/robots.txt`, `/sitemap.xml`, Open Graph, Schema.org, `/about`
- Production ops: Docker, Compose, Nginx, Kubernetes, Prometheus, GitHub Actions CI

## Quick start

```bash
cp .env.example .env
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python app.py
```

Open http://127.0.0.1:5000/

## Docker (recommended)

```bash
docker compose up --build -d
```

- Site (Nginx → Gunicorn): http://localhost:8080/
- Prometheus: http://localhost:9090/
- Grafana: http://localhost:3000/ (admin/admin locally)

Full runbook: [DEVOPS.md](./DEVOPS.md)

## Routes

| Path | Purpose |
| --- | --- |
| `/` | Home / spotlight / upcoming |
| `/categories` | Genre directory |
| `/genre/<id>` | Genre shelf + sort |
| `/movies` | Movies by year |
| `/series` | TV series archive |
| `/upcoming` | 2026 upcoming movies & series |
| `/series/watch/<id>` | Series trailer + legal guide |
| `/year/2010` | Curated year shelf |
| `/watch/<id>` | On-site trailer + legal HD guide |
| `/movie/<id>` | Details |
| `/search` | Catalog search |
| `/about` | Creator / project identity |
| `/robots.txt` | Crawler rules |
| `/sitemap.xml` | URL sitemap |
| `/healthz` | Liveness |
| `/readyz` | Readiness |
| `/metrics` | Prometheus |

## Google indexing

After deploy:

1. Confirm https://YOUR-DOMAIN/robots.txt and /sitemap.xml
2. Add the property in [Google Search Console](https://search.google.com/search-console)
3. URL Inspection → request indexing for `/`
4. Submit the sitemap

Buying `2daymovie.com` (or `.net`) and pointing it at Render is recommended for a clean brand URL.

## Deploy

- **Render** auto-deploys from `main`: https://twodaymovie.onrender.com/
- **Kubernetes**: `kubectl apply -f deploy/k8s/`
- **CI**: `.github/workflows/ci.yml` — tests, Docker build, Compose validate

## Legal note

Trailers are official YouTube embeds shown on this site (youtube-nocookie). “Stream in HD” opens TMDB’s licensed-provider guide. Pirate streaming sites are not supported. Titles without an on-site trailer are removed from browse/search catalogs.
