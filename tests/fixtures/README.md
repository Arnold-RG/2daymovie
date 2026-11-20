# Test fixtures

The source-channel denylist is **not** stored here. Tests load it from the
`CHANNELS_DENYLIST` environment variable, falling back to
`/workspace/shared/2daymovie-channels.json` on the shared agent box.

If that file is missing (for example in GitHub Actions), the denylist test
is skipped. The generic test that forbids `youtube.com/@` and
`youtube.com/channel/` links in rendered HTML, `static/`, and `templates/`
always runs.

Do not commit channel names, handles, or source URLs into this repository.
