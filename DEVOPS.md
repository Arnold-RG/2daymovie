# DevOps runbook — 2daymovie.to

Production-minded ops for the legal movie discovery app.

## Stack

| Layer | Choice |
| --- | --- |
| App | Flask + Gunicorn |
| Containers | Docker multi-stage-ready image + Compose |
| Edge | Nginx reverse proxy (Compose) |
| Orchestration | Kubernetes Deployment / Service / Ingress |
| Observability | `/healthz`, `/readyz`, Prometheus `/metrics`, Grafana |
| CI/CD | GitHub Actions (test → docker build → compose validate) |
| Cloud | Render (live), Fly.toml present, AWS-ready container |

Live: https://twodaymovie.onrender.com/

## Local (Linux / macOS / WSL / Git Bash)

```bash
cp .env.example .env   # add TMDB_API_KEY if you have one
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make test
make run
```

## Docker Compose (app + Nginx + Prometheus + Grafana)

```bash
cp .env.example .env
docker compose up --build -d
```

- App via Nginx: http://localhost:8080/
- Prometheus: http://localhost:9090/
- Grafana: http://localhost:3000/ (admin / admin — change in prod)

Stop: `docker compose down`

## Kubernetes

```bash
# Build & load image into your cluster first, then:
kubectl create secret generic twodaymovie-secrets \
  --from-literal=TMDB_API_KEY="$TMDB_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f deploy/k8s/deployment.yaml
kubectl rollout status deploy/twodaymovie
kubectl port-forward svc/twodaymovie 8080:80
```

Manifests include non-root user, dropped capabilities, read-only root FS, probes, and resource limits.

## Health & metrics

| Endpoint | Purpose |
| --- | --- |
| `GET /healthz` | Liveness |
| `GET /readyz` | Readiness (library catalog loaded) |
| `GET /metrics` | Prometheus scrape |

Nginx restricts `/metrics` to private networks in Compose.

## CI/CD

On every push/PR to `main`:

1. Install deps + `pytest`
2. Smoke `/healthz` `/readyz` `/metrics`
3. `docker build` + container health probe
4. `docker compose config` validation

Render auto-deploys from `main`.

## Security checklist

- Secrets via env / K8s Secret — never commit `.env`
- Security headers on every response (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`)
- Non-root container UID `10001`
- TLS at the edge (Render / Ingress `ssl-redirect`)
- Legal streaming only — TMDB watch providers, official YouTube trailers

## Networking notes

- App listens on `PORT` (default 8080 in containers)
- Compose: Nginx → `web:8080` on bridge network `edge`
- Prefer HTTPS in production; terminate TLS at load balancer / Ingress

## Monitoring

Prometheus scrapes `web:8080/metrics`. Grafana provisions the Prometheus datasource automatically from `deploy/monitoring/grafana/provisioning/`.
