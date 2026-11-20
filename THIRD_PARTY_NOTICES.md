# Third-party notices

2DayMovie ships **no vendored third-party JavaScript or CSS**. Everything in
`static/` is first-party code. Fonts are the visitor's system fonts.

## Bundled in the site

| Component | Where | License |
|---|---|---|
| Material Design Icons (path data for play, pause, volume, brightness, height, fullscreen, arrows, close, info, search icons) | inline `<svg>` in `templates/index.html`, `static/js/app.js` | Apache License 2.0, © Google LLC. https://github.com/google/material-design-icons/blob/master/LICENSE |

## Loaded at runtime (not redistributed)

| Component | Origin | Terms |
|---|---|---|
| YouTube IFrame Player API (`iframe_api`) | `https://www.youtube.com` | YouTube API Services Terms of Service: https://developers.google.com/youtube/terms/api-services-terms-of-service |
| YouTube embedded player (videos, thumbnails) | `https://www.youtube-nocookie.com`, `https://i.ytimg.com` | YouTube Terms of Service; each video stays under its owner's rights |

## Python (server, CI, tooling; not shipped to browsers)

| Package | License |
|---|---|
| Flask | BSD-3-Clause |
| python-dotenv | BSD-3-Clause |
| gunicorn | MIT |
| prometheus-client | Apache-2.0 |
| pytest (dev only, `requirements-dev.txt`) | MIT |
| yt-dlp (catalog refresh only, `scripts/requirements.txt`) | Unlicense |
