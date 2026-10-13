# 2daymovie

Official **HD movie and TV trailers** only — curated library, on-site embeds, no full-film streaming.

**2daymovie** is created and developed by **Arnold Rurangwa**.

- **Website:** https://arnold-rg.github.io/2daymovie/
- **Full server (shared reviews):** https://twodaymovie.onrender.com/
- **Creator:** Arnold Rurangwa

## Features

- Official HD trailers embedded on-site (YouTube nocookie)
- Categories, year shelves, series archive, upcoming titles
- Search across trailer-ready movies and series
- SEO: robots, sitemap, About, Open Graph
- Production ops: Docker, Compose, Nginx, Kubernetes, Prometheus, CI

We do **not** host copyrighted films or provide full-movie streaming.

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
| `/series/watch/<id>` | Series trailer room |
| `/year/2010` | Curated year shelf |
| `/watch/<id>` | On-site trailer room |
| `/movie/<id>` | Details |
| `/search` | Catalog search |
| `/reviews` | Live visitor reviews |
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

- **GitHub Pages** (public catalog): https://arnold-rg.github.io/2daymovie/
  The site is the `docs/` folder on `main`. Rebuild it with:

  ```bash
  BASE_PATH=/2daymovie \
  OFFICIAL_URL=https://arnold-rg.github.io/2daymovie/ \
  STATIC_EXPORT=1 \
  REVIEWS_LOCAL_ONLY=1 \
  python scripts/export_site.py --out docs
  ```

  Pages is already set to publish that folder. A workflow in `.github/workflows/pages.yml` can deploy the same build through GitHub Actions after **Settings → Pages → Build and deployment → Source** is switched to **GitHub Actions**. Until that switch, merging to `main` is what updates the live site.

  The public copy does not include the reviews database. Reviews typed there stay in the browser.

- **Render** auto-deploys from `main`: https://twodaymovie.onrender.com/
- **Reviews persistence:** set `DATABASE_URL` on Render, or place the Neon/Supabase URL in gitignored `data/official_database.url` (see `data/official_database.url.example`). Reviews also mirror to `data/site_vault.json` for local backup.
- **Kubernetes**: `kubectl apply -f deploy/k8s/`
- **CI**: `.github/workflows/ci.yml` — tests, Docker build, Compose validate

## Legal note

Trailers are official embeds shown on this site. We do not host or stream full films. Titles without an on-site trailer are removed from browse/search catalogs.
