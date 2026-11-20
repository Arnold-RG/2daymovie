#!/usr/bin/env python3
"""Flag dead or non-embeddable YouTube ids in catalog.json and trailers.json.

Checks, for every id:
  1. YouTube oEmbed (https://www.youtube.com/oembed?url=...&format=json)
       200 = embeddable
       401 = embedding disabled
       404 / 400 = dead or private
  2. Thumbnail https://i.ytimg.com/vi/<id>/hqdefault.jpg
       404 = dead
       200 with a 120x90 placeholder = typically a missing video

Rate-limited, retries on 429, prints a table, optional JSON. Exits nonzero
if any id is bad.

Usage:
  python scripts/check_videos.py
  python scripts/check_videos.py --json docs/video-check-results.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parent.parent
YT_ID_LEN = 11
OEMBED = "https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={id}&format=json"
THUMB = "https://i.ytimg.com/vi/{id}/hqdefault.jpg"
USER_AGENT = "2DayMovie-video-check/1.0 (+https://github.com/Arnold-RG/2daymovie)"
# YouTube's "video does not exist" hqdefault placeholder is 120x90.
PLACEHOLDER_WIDTH = 120
PLACEHOLDER_HEIGHT = 90


@dataclass
class Result:
    youtube_id: str
    source: str  # catalog | trailers
    oembed_status: int | None
    oembed_verdict: str
    thumb_status: int | None
    thumb_verdict: str
    ok: bool
    detail: str = ""


class RateLimiter:
    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._lock = Lock()
        self._next = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + self.min_interval
        if delay > 0:
            time.sleep(delay)


def jpeg_size(data: bytes) -> tuple[int, int] | None:
    """Return (width, height) from a JPEG SOF marker, or None."""
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 8 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h = int.from_bytes(data[i + 5 : i + 7], "big")
            w = int.from_bytes(data[i + 7 : i + 9], "big")
            return w, h
        if marker in (0xD8, 0xD9) or (0xD0 <= marker <= 0xD7) or marker == 0x01:
            i += 2
            continue
        if i + 3 >= len(data):
            break
        seglen = int.from_bytes(data[i + 2 : i + 4], "big")
        i += 2 + seglen
    return None


def http_get(url: str, timeout: float, limiter: RateLimiter, retries: int = 3) -> tuple[int, bytes]:
    limiter.wait()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    last_status = None
    last_err = ""
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            last_status = exc.code
            last_err = exc.reason if isinstance(exc.reason, str) else str(exc.reason)
            body = b""
            try:
                body = exc.read() or b""
            except Exception:
                pass
            if exc.code == 429 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                limiter.wait()
                continue
            return exc.code, body
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = type(exc).__name__
            if attempt < retries - 1:
                time.sleep(1 + attempt)
                continue
            return None, last_err.encode()  # type: ignore[return-value]
    return last_status, last_err.encode()


def oembed_verdict(status: int | None) -> tuple[str, str]:
    if status == 200:
        return "embeddable", ""
    if status == 401:
        return "embedding_disabled", "oEmbed 401: embedding disabled"
    if status in {400, 404}:
        return "dead_or_private", f"oEmbed {status}: dead or private"
    if status is None:
        return "error", "oEmbed request failed"
    return "unexpected", f"oEmbed HTTP {status}"


def thumb_verdict(status: int | None, body: bytes) -> tuple[str, str]:
    if status in {400, 404}:
        return "missing", f"thumbnail HTTP {status}"
    if status != 200 or not body:
        return "error", f"thumbnail HTTP {status}"
    size = jpeg_size(body)
    if size == (PLACEHOLDER_WIDTH, PLACEHOLDER_HEIGHT):
        return "placeholder", "hqdefault.jpg is the 120x90 missing-video placeholder"
    if size is None:
        return "unknown", "thumbnail was not a readable JPEG"
    return "ok", ""


def collect_ids(catalog: Path, trailers: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    if catalog.is_file():
        doc = json.loads(catalog.read_text(encoding="utf-8"))
        for item in doc.get("items", doc if isinstance(doc, list) else []):
            ident = item.get("id")
            if ident and ident not in seen:
                seen.add(ident)
                found.append((ident, "catalog"))
    if trailers.is_file():
        doc = json.loads(trailers.read_text(encoding="utf-8"))
        for item in doc.get("items", doc if isinstance(doc, list) else []):
            ident = item.get("youtube_id") or item.get("id")
            if ident and ident not in seen:
                seen.add(ident)
                found.append((ident, "trailers"))
    return found


def check_one(ident: str, source: str, timeout: float, limiter: RateLimiter) -> Result:
    o_status, o_body = http_get(OEMBED.format(id=ident), timeout, limiter)
    if isinstance(o_status, str):  # shouldn't happen
        o_status = None
    o_verdict, o_detail = oembed_verdict(o_status)
    t_status, t_body = http_get(THUMB.format(id=ident), timeout, limiter)
    if isinstance(t_status, str):
        t_status = None
    t_verdict, t_detail = thumb_verdict(t_status, t_body if isinstance(t_body, bytes) else b"")
    detail = "; ".join(x for x in (o_detail, t_detail) if x)
    # Bad if oEmbed says disabled/dead, or the thumbnail is missing/placeholder
    # while oEmbed is also not 200. A 200 oEmbed with a placeholder is unusual
    # but we still flag the placeholder.
    bad = o_verdict in {"embedding_disabled", "dead_or_private", "error"} or t_verdict in {
        "missing",
        "placeholder",
    }
    # If oEmbed is embeddable and the thumb is a real image (or unknown JPEG), it's ok.
    if o_verdict == "embeddable" and t_verdict in {"ok", "unknown"}:
        bad = False
    return Result(
        youtube_id=ident,
        source=source,
        oembed_status=o_status if isinstance(o_status, int) else None,
        oembed_verdict=o_verdict,
        thumb_status=t_status if isinstance(t_status, int) else None,
        thumb_verdict=t_verdict,
        ok=not bad,
        detail=detail,
    )


def format_table(results: list[Result]) -> str:
    bad = [r for r in results if not r.ok]
    lines = []
    header = f"{'id':<13} {'source':<9} {'oembed':<7} {'o_verdict':<20} {'thumb':<7} {'t_verdict':<14} detail"
    lines.append(header)
    lines.append("-" * len(header))
    rows = bad or results[:0]  # table of bad rows; if all ok, say so
    if not bad:
        lines.append("(no bad ids)")
    for r in bad:
        lines.append(
            f"{r.youtube_id:<13} {r.source:<9} {str(r.oembed_status or '-'):<7} "
            f"{r.oembed_verdict:<20} {str(r.thumb_status or '-'):<7} {r.thumb_verdict:<14} {r.detail}"
        )
    ok = sum(1 for r in results if r.ok)
    lines.append("")
    lines.append(
        f"checked={len(results)} ok={ok} bad={len(bad)} "
        f"embedding_disabled={sum(1 for r in results if r.oembed_verdict=='embedding_disabled')} "
        f"dead_or_private={sum(1 for r in results if r.oembed_verdict=='dead_or_private')} "
        f"placeholder_thumbs={sum(1 for r in results if r.thumb_verdict=='placeholder')}"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT / "data" / "catalog.json")
    parser.add_argument("--trailers", type=Path, default=ROOT / "data" / "trailers.json")
    parser.add_argument("--json", dest="json_out", type=Path, default=None, help="Write full JSON report")
    parser.add_argument("--delay", type=float, default=0.2, help="Minimum seconds between HTTP requests")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)

    ids = collect_ids(args.catalog, args.trailers)
    if not ids:
        print("No youtube ids found in catalog/trailers", file=sys.stderr)
        return 2

    limiter = RateLimiter(args.delay)
    results: list[Result] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futs = {pool.submit(check_one, ident, source, args.timeout, limiter): ident for ident, source in ids}
        for i, fut in enumerate(as_completed(futs), 1):
            results.append(fut.result())
            if i % 50 == 0 or i == len(futs):
                print(f"... {i}/{len(futs)} checked", file=sys.stderr)

    # Stable order: catalog then trailers, original order
    order = {ident: i for i, (ident, _) in enumerate(ids)}
    results.sort(key=lambda r: order[r.youtube_id])

    table = format_table(results)
    print(table)

    payload = {
        "checked": len(results),
        "ok": sum(1 for r in results if r.ok),
        "bad": sum(1 for r in results if not r.ok),
        "results": [asdict(r) for r in results],
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.json_out}", file=sys.stderr)

    return 1 if any(not r.ok for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
