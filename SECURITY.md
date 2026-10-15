# Security Policy

## Product scope

**2daymovie** is a legal movie and TV **trailer discovery** site. It embeds official HD trailers and, when available, shows **where to watch** links from public metadata (TMDB). It does **not** host, stream, or redistribute full films.

## Supported versions

Security fixes land on the `main` branch and deploy to:

- Live app: https://twodaymovie.onrender.com/
- GitHub Pages: https://arnold-rg.github.io/2daymovie/

## Reporting a vulnerability

Email **Arnold Rurangwa** via ARNOVA Group (Kigali) or open a private GitHub security advisory on [Arnold-RG/2daymovie](https://github.com/Arnold-RG/2daymovie).

Please include:

1. Description and impact
2. Steps to reproduce
3. Affected URL or commit SHA if known

We aim to acknowledge reports within **7 days** and ship fixes as soon as practical.

## Hardening practices

- Secrets stay in environment variables / Render secrets — never commit `.env`, API keys, or database URLs
- Flask templates use Jinja2 autoescape; visitor text is escaped in reviews UI
- External outbound links use `rel="noopener noreferrer"`
- HTTP security headers: CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`
- Static Pages builds also ship a CSP meta tag and `referrer` meta
- Review forms use maxlength, honeypot, and server-side validation

## Free / public APIs

Documented in `.env.example`. Optional `TMDB_API_KEY` unlocks live metadata and watch providers. Without a key, the curated offline catalog still serves trailers.
