# 2daymovie.to

Legal movie discovery — curated **2000–2026** library, **official full trailers**, and **licensed HD streaming guides**. No accounts. We do **not** host copyrighted films.

**Official live site:** https://twodaymovie.onrender.com/

## Features

- Cinema-grade UI: full-bleed heroes, year archive, immersive Watch rooms
- Library timeline for every year from 2000 → 2026
- Watch room: official full YouTube trailer + TMDB legal HD stream guide
- Search / browse / genres via TMDB when `TMDB_API_KEY` is set
- Production ops: Docker, Compose, Nginx, Kubernetes, Prometheus metrics, GitHub Actions CI

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
| `/` | Home / spotlight |
| `/library` | Year timeline |
| `/year/2010` | Curated year shelf |
| `/watch/<id>` | Trailer + legal HD guide |
| `/movie/<id>` | Details |
| `/healthz` | Liveness |
| `/readyz` | Readiness |
| `/metrics` | Prometheus |

## Deploy

- **Render** auto-deploys from `main`: https://twodaymovie.onrender.com/
- **Kubernetes**: `kubectl apply -f deploy/k8s/`
- **CI**: `.github/workflows/ci.yml` — tests, Docker build, Compose validate

## Legal note

Trailers are official YouTube embeds via TMDB. “Stream in HD” opens TMDB’s licensed-provider guide. Pirate streaming sites are not supported.
