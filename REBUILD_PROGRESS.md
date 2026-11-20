# 2DayMovie — rebuild progress

> **Status: In development. Not released.** This is a public, reviewable record of confirmed work, not a claim that the application is ready.

## Live links

- [Current production website](https://arnold-rg.github.io/2daymovie/) — **old published version**
- [Development branch](https://github.com/Arnold-RG/2daymovie/tree/development/streaming-rebuild)
- [Development commit history](https://github.com/Arnold-RG/2daymovie/commits/development/streaming-rebuild/)
- [Changes compared with production](https://github.com/Arnold-RG/2daymovie/compare/main...development/streaming-rebuild)
- [Backup branch](https://github.com/Arnold-RG/2daymovie/tree/backup/pre-rebuild-20261120)

## Feature checklist

| Feature | State | Evidence |
|---|---|---|
| Original version preserved | Done | Backup branch exists |
| Isolated rebuild branch | Done | Development branch exists |
| Original black/red/platinum colors | Preserved | No rebranding requested |
| On-site player interface | Code present; playback unverified | `templates/index.html` |
| Navigation, footer and metadata cleanup | Code present; untested | `templates/base.html` |
| Homepage search and category filters | Code present; untested | `templates/index.html` |
| Candidate full-length video catalog | 3 candidates; 0 publishable verified | `services/streaming_catalog.py` |
| Popularity ranking | Module written; not integrated | `services/popularity.py` |
| Complete season/episode player | Not done | — |
| 100 verified movie/series links | Not done | — |
| Global 10,800+ African catalog | Not done | — |
| AI animation and kids catalog | Not done | — |
| Automatic YouTube metadata updates | Not done | — |
| Browser playback, mobile, security tests | Not verified | — |
| Production deployment of rebuild | Not done | — |

## Publishing rules

1. Do not describe a video as a complete movie or episode until its runtime and content have been checked.
2. Do not count a video as publishable until embedding and rights review have been completed.
3. Use official YouTube embeds, not unauthorized downloads or circumvention.
4. Keep the original colors.
5. Deploy only after functional and security testing.
6. Update this file alongside every substantial development milestone. GitHub commit history is the authoritative record of what actually changed.

_Last manually reviewed: 2026-11-20. This file does not update itself automatically._
