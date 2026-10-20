# Security Policy

## Supported versions

Security updates apply to the latest commit on the default branch of this repository.

## Reporting a vulnerability

Email **rurangwaarnold32@gmail.com** with:

- Repository name and affected URL/path
- Description and impact
- Steps to reproduce (proof of concept if available)

Please do **not** open a public issue for unpatched vulnerabilities.

We aim to acknowledge reports within 7 days and publish a fix or mitigation when confirmed.

## Practice

- No secrets in source; use `.env.example` only
- Prefer `textContent` over `innerHTML` for untrusted data
- External links use `rel="noopener noreferrer"`
- Dependabot / Actions least privilege where applicable

## Deployment boundaries

- Supply a unique `SECRET_KEY` through your host's secret store if sessions are used;
  the unset fallback is random per process and is unsuitable for shared sessions.
- Review throttling uses the socket peer address. Do not trust arbitrary forwarded
  headers. Behind a proxy, configure rate limits at that trusted edge; the current
  in-process throttle is not a distributed abuse prevention system.
- Compose monitoring ports bind only to loopback. Set `GRAFANA_ADMIN_PASSWORD`
  before starting Compose. Protect remote monitoring access with authentication/TLS.
- Keep databases, review backups, and credential files outside image build contexts.
- GitHub Pages does not apply Flask response headers. Configure hosting controls
  separately; the presence of Flask CSP does not secure the static deployment.

## Public and private boundaries

See [platform direction](PLATFORM.md) for data boundaries, release requirements and proposed next actions.
