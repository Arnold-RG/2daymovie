# 2DayMovie — Movie Discovery Web App

**Flask web backend with container deployment** · [GitHub repository](https://github.com/Arnold-RG/2daymovie)

## What this project does

Python/Flask movie-oriented web application with server templates, static assets, tests, Docker packaging and deployment configuration. Live external API availability and content rights require verification.

**Primary stack:** Flask, Gunicorn, PostgreSQL adapter, Docker/Compose, Python tests.

> **Project verification:** This README describes observed source structure and release expectations. Not every feature, dependency or target device has been certified. Consult actual CI results and source before making public claims.

## Repository architecture

| File or directory | Purpose |
| --- | --- |
| `app.py` | Flask application entry |
| `templates/` | Server-rendered views |
| `static/` | Browser assets |
| `services/` | Services and external integrations |
| `tests/` | Automated checks |
| `Dockerfile` | Container build |
| `docker-compose.yml` | Local multi-service orchestration |
| `requirements.txt` | Python dependency pins |
| `DEVOPS.md` | Operational notes |

## Local development

Install Git and the required language runtime. Use a clean environment and review configuration files for secrets before starting network services.

```sh
python -m venv .venv
# Activate .venv
python -m pip install -r requirements.txt
python -m pytest
# Review .env.example and service requirements before running the app
```

**Environment note:** Review configured environment variables and Docker Compose services before launching anything. A local pytest run does not certify production.

## User experience and core requirements

- Provide responsive search, discovery and meaningful empty/error states.
- Label metadata, movie details and availability according to the actual provider/source.
- Secure external API rate limits and service failures without false availability claims.

Build for real customer journeys: clear navigation, accessible controls, responsive layouts, truthful claims, human-readable errors and meaningful loading/empty states.

## Security, data and privacy

- Keep database strings and external API tokens in environment-specific secret stores.
- Implement input validation, escaping, CSRF defenses and session controls where applicable.
- Only display movie images/metadata with appropriate rights and attribution.

Review secrets, trust boundaries, external services and permission handling. Use scoped credentials, a private disclosure channel (see `SECURITY.md` if present), and secure dependency updates.

## Quality and operations

| Area | Release acceptance criterion |
| --- | --- |
| Implementation | Maintainable code, clear ownership, documented configuration |
| Testing | Actual unit/integration checks or a documented repeatable smoke test |
| Security | Input and dependency checks, least privilege and no exposed credentials |
| Accessibility | Keyboard, contrast, touch and responsive testing for user-facing screens |
| CI/CD | Reproducible builds, protected release jobs, owner-approved publication |
| Reliability | Error monitoring; backups/recovery for persisted data; rollback plan |

**These are intended gates, not an assertion of passing tests.** Kubernetes is unnecessary for purely static pages; reassess it only where multi-service infrastructure warrants the complexity.

## Next engineering milestones

1. Test API/service integration with mocks and retries.
2. Harden Docker image and container privileges.
3. Add health checks, production logging, database backup/restore and releases.

## Contributions and release policy

Use reviewable branches and pull requests. Don't add unlicensed visual assets, mock client testimonials, private customer data or unverified integrations. Owners approve public releases; note remaining limitations in the release report.
