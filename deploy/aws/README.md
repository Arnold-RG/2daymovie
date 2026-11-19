# AWS notes for containerized 2daymovie

This app is a portable container. Prefer:

1. **ECR** — push `twodaymovie:latest`
2. **ECS Fargate** or **EKS** — run the image with env secrets from **Secrets Manager** / **SSM**
3. **ALB** — HTTPS listener + target group health check on `/healthz`
4. **IAM** — task role with least privilege (no S3 needed unless you add assets)
5. **VPC** — private subnets for tasks, public for ALB; security groups allow 443→ALB→8080

Minimal ECS task env:

```
PORT=8080
FLASK_DEBUG=0
TMDB_API_KEY=<from Secrets Manager>
TMDB_WATCH_REGION=US
OFFICIAL_URL=https://your-domain
```

Health check: `GET /healthz`  
Ready check: `GET /readyz`  
Metrics: scrape `/metrics` with Prometheus on EKS or Amazon Managed Prometheus.
