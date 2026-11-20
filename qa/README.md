# QA artifacts

This directory holds Sentinel's security review, manual QA checklist, and
video-check results.

They are not under `docs/`. `docs/` is the static site written by
`scripts/export_site.py` and compared in CI (`diff -r` against a fresh
export). Putting markdown reviews in `docs/` would break that check and
would publish them on GitHub Pages.
