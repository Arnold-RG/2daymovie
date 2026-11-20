# Video embed check results

Ran `python scripts/check_videos.py --delay 0.2 --workers 4` once against
the catalog and trailers on this branch.

- Date: 20 Nov 2026, 22:27–22:36 Europe/Warsaw (~9 minutes)
- Method: YouTube oEmbed
  (`https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=ID&format=json`)
  plus `https://i.ytimg.com/vi/ID/hqdefault.jpg` (flag 401 as embedding
  disabled, 400/404 as dead or private, and a 120×90 placeholder thumb
  as a missing video)
- Checked: 1062 ids (1053 catalog, 9 trailers; unique)
- oEmbed: 1062 HTTP 200 (embeddable)
- Thumbnails: 1062 HTTP 200, real `hqdefault` JPEGs (not the 120×90 placeholder)
- Bad ids: 0
- Exit code: 0

No ids were disabled, dead, private, or missing a thumbnail at the time
of this run. Re-run the script before a production push; results can
change as YouTube rights and privacy settings change.
