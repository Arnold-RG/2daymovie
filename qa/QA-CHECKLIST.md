# 2DayMovie QA checklist

Manual desktop and mobile pass for the Netflix-style rebuild. Automated
pytest coverage lives in `tests/` and is not a substitute for this list.
Run this pass against a Forge preview (Flask or the static export) once
the URL is shared. Record the preview URL, date (Europe/Warsaw), viewport,
browser, and pass / fail / n/a for every item.

## Environments

- [ ] Local Flask (`/healthz` 200, `/readyz` 200)
- [ ] Render web service (note cold start: first request after idle)
- [ ] GitHub Pages / static export, if still in use
- [ ] 404 page on each host (`/this-is-not-a-page`)

## Breakpoints

For each viewport below: layout, nav, hero, rows, search, and player.

| Viewport | Device metaphor | Pass? | Notes |
| --- | --- | --- | --- |
| 360 × 640 | small phone | | |
| 768 × 1024 | tablet / large phone | | |
| 1280 × 800 | laptop | | |
| 1920 × 1080 | desktop | | |

Check at each width:

- [ ] Brand, section links, and search remain usable (hamburger at 360)
- [ ] Hero fills the viewport reasonably; arrows / dots do not overflow
- [ ] Category rows scroll horizontally without trapping the page scroll
- [ ] Cards do not clip titles unreadably; “See all” works
- [ ] Footer and legal line stay readable
- [ ] No horizontal page overflow (except the intended row scroller)

## Keyboard and focus

- [ ] Skip link (“Skip to content”) is visible on first Tab and moves focus to `#main`
- [ ] All interactive controls are reachable in a logical order (nav, search, hero arrows/dots, row cards, See all, player)
- [ ] Focus rings are visible on dark backgrounds (contrast against `#0b0b0f`)
- [ ] Hero: Left / Right arrows change slide when the hero is focused
- [ ] Search: typing filters; Esc or “Back to browse” returns to rows and restores scroll
- [ ] Modal: opening moves focus to Close; Tab is trapped in the dialog; Esc closes; focus returns to the control that opened it
- [ ] Closing the modal via backdrop click also restores focus
- [ ] Off-screen hero iframes are not in the tab order (`tabIndex=-1`)

## Hero / autoplay (WCAG 2.2.2)

The hero auto-advances muted trailer clips (~30s). WCAG 2.2.2 requires a
user-visible pause (or stop) for content that moves automatically for more
than five seconds.

- [ ] A Pause / Play control is present and keyboard-accessible
- [ ] Pause stops auto-advance and pauses the current clip
- [ ] `prefers-reduced-motion: reduce` is honoured (no large slide motion)
- [ ] Autoplay is muted; unmuting is an explicit user action
- [ ] Switching tabs (`visibilitychange`) pauses the clip
- [ ] Opening search results or the player pauses the hero

## Player modal

- [ ] Open from a catalog card, a “See all” result, and “Watch trailer”
- [ ] Embed URL is `https://www.youtube-nocookie.com/embed/...` (DevTools)
- [ ] Iframe has `sandbox="allow-scripts allow-same-origin"`
- [ ] No download / “save video” / rehosted `mp4` or proxy
- [ ] Error state appears if the video cannot play
- [ ] Close via button, backdrop, and Esc; body scroll is restored
- [ ] Deep link `?v=<id>` opens the matching title only if that id is in the catalog; junk ids do nothing

## Captions and media text

- [ ] YouTube captions / CC control is available in the official player
- [ ] Hero posters have empty `alt` only when the adjacent text already names the film; otherwise a short alt
- [ ] Card images have useful `alt` (title, not “image”)
- [ ] Decorative SVGs are `aria-hidden="true"`
- [ ] Modal title and metadata match the selected item

## Contrast, typography, and motion

- [ ] Body text and nav links meet WCAG 2.2 AA against the dark background
- [ ] Muted/secondary text (footer, dates, genre labels) also meets AA
- [ ] The red primary button (`#e50914` or similar) with white text meets AA
- [ ] Focus rings meet 3:1 against adjacent colour
- [ ] Placeholder search text is not the only way to know the field’s purpose (a visible label or `sr` label exists)
- [ ] No flashing content faster than three times per second

## Images and performance

- [ ] Thumbnails use lazy loading except the first hero / first row (LCP)
- [ ] `preconnect` to `https://www.youtube-nocookie.com` and `https://i.ytimg.com` is present
- [ ] Broken thumbnail fallback (hqdefault after maxresdefault) works
- [ ] Lighthouse (mobile and desktop) on the preview: record Performance and Accessibility scores; fix anything below 90 accessibility or a serious performance diagnostic (render-blocking, unsized images, huge hero videos on cellular)
- [ ] Render cold start: hit `/healthz` after idle; record wait time. `/readyz` should return ready once `catalog.json` is readable. Document if the first document request is significantly slower than later ones.

## Search

- [ ] Empty query / under two characters does not show a bogus full-catalog dump (current client: hides results until two characters, or submit)
- [ ] Ordinary title queries return only items that exist in `catalog.json` or `trailers.json`
- [ ] Junk and XSS strings (`<script>alert(1)</script>`, `"<img onerror=...>`) do not execute; the query is escaped if shown in “Results for …”
- [ ] A query that matches nothing shows the empty state
- [ ] There is no server search endpoint today; if Forge adds `/api/search` (or similar), re-run `tests/test_search.py` and this section against it

## 404 and legacy URLs

- [ ] Unknown paths render the 404 page (not a stack trace)
- [ ] 404 offers a working Home link on Flask and on GitHub Pages (`/<repo>/`)
- [ ] Legacy prefixes (`/library`, `/movies`, `/watch/...`, `/search`, `/upcoming`, …) redirect to `/` with 301

## Source-channel leak (manual)

Automated tests cover static files and server-rendered HTML. Also check the
live DOM after the catalog loads:

- [ ] No channel names, `@handles`, or `youtube.com/@` / `youtube.com/channel/` links in the visible UI, tooltips, `aria-label`s, or page source after browse + search + player open
- [ ] Row headings come from genres, not source names
- [ ] Footer does not credit source channels by name

Do not paste any matching names into tickets or this checklist; refer to
counts and a private note if a hit is found.

## Security headers (preview)

- [ ] `X-Content-Type-Options: nosniff`
- [ ] `Referrer-Policy` present
- [ ] `Content-Security-Policy` with `frame-src https://www.youtube-nocookie.com` only, `object-src 'none'`, `base-uri`, `frame-ancestors`, and no `unsafe-inline` / `unsafe-eval` (expected fail until Forge adds it)
- [ ] `Strict-Transport-Security` on the HTTPS Render host
- [ ] `Permissions-Policy` present
- [ ] Mixed content: none. All embeds, thumbs, and scripts are HTTPS.

## Sign-off

| Item | Result |
| --- | --- |
| Preview URL | |
| Date (Europe/Warsaw) | |
| Tester | |
| Blockers | |
| Ready for the repository owner's OK to push / PR? | no / yes (advisory) |
