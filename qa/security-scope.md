# Security scope for 2DayMovie

2DayMovie is a static-first catalog of official YouTube embeds: a Flask app
(also exported as static pages for Render and GitHub Pages), no user accounts,
no database, no payments, no uploads, no AI features and no physical devices.
Of the five standing areas, three apply and two do not.

| Area | Applies? | Why |
|---|---|---|
| GRC | **Yes** | The site is public and embeds other people's videos, so licensing, privacy and disclosure must be clear. |
| Cloud | **Yes** | It runs on Render (and has Docker, Fly, k8s and AWS configs) and is built by GitHub Actions. |
| IAM | **Partly** | There are no user accounts. The only credentials are operator ones: the `/metrics` token and the local Grafana admin. |
| AI Security | N/A | No AI or ML model, prompt, or AI API is used; "AI" is only a content category name. |
| OT | N/A | No operational technology, industrial control or physical device is involved. |

## GRC

- **LICENSE:** MIT for the code, Copyright (c) 2026 Arnold Rurangwa. README and
  THIRD_PARTY_NOTICES state that video content belongs to its owners and is not
  covered by it.
- **Privacy:** a Privacy section is in the site footer (`#privacy`). It says there are no accounts, no
  analytics and no tracking cookies of our own; the site sets no cookies (tested); videos come from
  `youtube-nocookie.com`; `localStorage` key `tdm.hero.v1` holds only the header
  video's sound, volume, brightness and size choices (tested).
- **YouTube cookies (measured):** a headless load of the home page ends with
  YouTube's own cookies on `.youtube.com` (`YSC`, `VISITOR_INFO1_LIVE`,
  `VISITOR_PRIVACY_METADATA`, `__Secure-YNID`, `__Secure-ROLLOUT_TOKEN`), because the
  header autoplays and the IFrame API script loads from `www.youtube.com`.
  `youtube-nocookie` reduces tracking but does not stop this. The privacy note says so
  plainly. **Fixed with click-to-load:** with no stored consent the hero shows posters and a
  "Play trailer" button with the line "Video by YouTube, loads YouTube cookies", and nothing
  is requested from `youtube.com` or `youtube-nocookie.com` (headless check: zero requests,
  zero YouTube cookies before the click). The first click or tap on Play trailer or on any
  video stores `yt_consent` = `1` in localStorage, and later visits autoplay as before.
  A shared `?v=` link opens the player with a "Play video" button instead of the embed.
  Thumbnails still load from `i.ytimg.com`, which sets no cookies.
- **Content rights:** the footer says every video is an official YouTube embed,
  nothing is rehosted, and each video stays under its owner's rights and YouTube's terms.
- **Third-party licenses:** no vendored JS or CSS. Icon path data is Material
  Design Icons (Apache-2.0), credited in `THIRD_PARTY_NOTICES.md` with the Python
  dependencies and the runtime YouTube API terms.
- **robots.txt:** allows the public site; disallows the operator endpoints
  (`/metrics`, `/healthz`, `/readyz`).
- **security.txt:** `/.well-known/security.txt` (RFC 9116) with Contact, Expires
  (2027-11-20, renew yearly), Preferred-Languages and Policy (`SECURITY.md`). It is
  served by Flask and exported with the static pages. On GitHub Pages it sits under
  `/2daymovie/`, so it only counts on a root-hosted domain such as Render.

## Cloud

- **Secrets:** a gitleaks-style regex scan of every tracked file and of the full
  history (`git log -p --all`) for AWS, GitHub, Slack, Google and OpenAI-style keys, private
  keys and `password` / `token` / `api_key` assignments found only placeholders
  (`your_tmdb_v3_api_key_here`, `ci-validation-only`, a file path). A test
  repeats the scan on tracked files.
- **Env config:** `render.yaml` marks `METRICS_TOKEN` `sync: false`; no secret
  values. `docker-compose.yml` takes the Grafana password and metrics token
  from env (`${GRAFANA_ADMIN_PASSWORD:?…}` fails fast if unset).
- **Docker image:** runs as uid 10001 (`USER appuser`), with no extra OS packages
  (curl is removed; the health check uses Python). Code is root-owned and read-only for the app user. `pytest` moved to
  `requirements-dev.txt` so it is not installed in the image. `.dockerignore`
  keeps tests, QA docs, CI files, `.env` and the untracked private data
  files out of the build context.
- **/metrics:** private, token from `METRICS_TOKEN`; otherwise 404.
- **CI:** all actions are pinned to commit SHAs. `ci.yml` and `qa.yml` use
  `contents: read`. `pages.yml` now has `permissions: {}` at the top; the build
  job gets `contents: read` and `pages: read`, and only the deploy job gets
  `pages: write` and `id-token: write`.
- **Known history note:** `scripts/channels.json` (the private channel list, not a
  secret) still exists in history from the first skeleton commit `c0134986`.
  Removing it would mean rewriting history and force-pushing, which needs the owner's approval.

## IAM

- No user accounts, sign-in, sessions or roles exist, so there is no user IAM.
- No default credentials remain: Grafana needs `GRAFANA_ADMIN_PASSWORD` (compose
  refuses to start without it), and the docs no longer suggest `admin / admin`.
- The `/metrics` token is required and must be strong: tokens shorter than 32
  characters are treated as unset and the endpoint returns 404 (tested). It is compared in constant time.
- No further IAM scope applies.

## AI Security

N/A: the site has no AI or ML model, prompt or AI API.

## OT

N/A: no operational technology, industrial control system or device is involved.
