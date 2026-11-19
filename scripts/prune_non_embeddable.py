"""Remove YouTube trailer keys that refuse on-site embeds.

Uses watch-page playableInEmbed + oEmbed. Titles left with no
embeddable trailer are removed from the catalog.
"""

from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
YEAR_OUT = ROOT / "data" / "year_catalog.json"
SERIES_OUT = ROOT / "data" / "series_catalog.json"
CACHE_PATH = ROOT / "data" / "_embed_cache.json"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
YT_KEY = re.compile(r"^[A-Za-z0-9_-]{11}$")
PLAYABLE_RE = re.compile(r'"playableInEmbed"\s*:\s*(true|false)')
WORKERS = 8


def looks_like_key(key: str | None) -> bool:
    if not key or not YT_KEY.fullmatch(key):
        return False
    if key.startswith("mobile") or "web-" in key or key.endswith("-"):
        return False
    return True


def is_embeddable(key: str, session: requests.Session) -> bool:
    """True only when the trailer can play inside a third-party iframe."""
    try:
        oe = session.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={key}", "format": "json"},
            timeout=18,
        )
        if oe.status_code != 200:
            return False
    except Exception:
        return False

    try:
        watch = session.get(
            f"https://www.youtube.com/watch?v={key}",
            timeout=20,
        )
        text = watch.text or ""
    except Exception:
        return False

    match = PLAYABLE_RE.search(text)
    if match and match.group(1) == "false":
        return False

    lowered = text.lower()
    if "playback on other websites has been disabled" in lowered:
        return False

    # Removed / private / region-blocked often lack a usable player response.
    if '"playabilitystatus"' in lowered.replace(" ", ""):
        if '"status":"error"' in lowered.replace(" ", "") or '"status":"login_required"' in lowered.replace(
            " ", ""
        ):
            # login_required alone is common for age gates; only fail if also not playable
            if match is None:
                return False
    return True


def load_cache() -> dict[str, bool]:
    if not CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return {k: bool(v) for k, v in data.items() if looks_like_key(k)}
    except Exception:
        return {}


def save_cache(cache: dict[str, bool]) -> None:
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def collect_keys(paths: list[Path]) -> set[str]:
    keys: set[str] = set()
    for path in paths:
        rows = json.loads(path.read_text(encoding="utf-8"))
        for row in rows:
            for key in list(row.get("trailer_keys") or []) + [row.get("trailer_key")]:
                if looks_like_key(key):
                    keys.add(key)
    return keys


def resolve_keys(keys: set[str], cache: dict[str, bool], force: bool = False) -> dict[str, bool]:
    pending = sorted(keys) if force else [k for k in sorted(keys) if k not in cache]
    print(f"Checking {len(pending)} keys…", flush=True)
    if not pending:
        return cache

    done = 0
    blocked = 0

    def work(key: str) -> tuple[str, bool]:
        session = requests.Session()
        session.headers.update(HEADERS)
        ok = is_embeddable(key, session)
        time.sleep(0.04)
        return key, ok

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(work, k): k for k in pending}
        for fut in as_completed(futures):
            key, ok = fut.result()
            cache[key] = ok
            done += 1
            if not ok:
                blocked += 1
                print(f"  [{done}/{len(pending)}] BLOCKED {key}", flush=True)
            elif done % 40 == 0:
                print(f"  [{done}/{len(pending)}] OK… ({blocked} blocked so far)", flush=True)
            if done % 40 == 0:
                save_cache(cache)

    save_cache(cache)
    return cache


def prune_file(path: Path, cache: dict[str, bool]) -> None:
    rows = json.loads(path.read_text(encoding="utf-8"))
    kept_rows: list[dict] = []
    dropped_titles = 0
    dropped_keys = 0

    for row in rows:
        raw: list[str] = []
        for key in list(row.get("trailer_keys") or []) + [row.get("trailer_key")]:
            if looks_like_key(key) and key not in raw:
                raw.append(key)
        good = [k for k in raw if cache.get(k) is True]
        dropped_keys += len(raw) - len(good)
        if not good:
            dropped_titles += 1
            continue
        row["trailer_keys"] = good
        row["trailer_key"] = good[0]
        kept_rows.append(row)

    path.write_text(json.dumps(kept_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    multi = sum(1 for r in kept_rows if len(r.get("trailer_keys") or []) > 1)
    print(
        f"{path.name}: kept {len(kept_rows)} titles "
        f"({dropped_titles} removed, {dropped_keys} blocked keys, {multi} multi-trailer)",
        flush=True,
    )


def main() -> int:
    force = "--force" in sys.argv
    paths = [YEAR_OUT, SERIES_OUT]
    cache = {} if force else load_cache()
    if force and CACHE_PATH.exists():
        CACHE_PATH.unlink()
    keys = collect_keys(paths)
    cache = resolve_keys(keys, cache, force=force)
    blocked = sum(1 for k in keys if cache.get(k) is False)
    print(f"Embeddable: {len(keys) - blocked}/{len(keys)}  blocked: {blocked}", flush=True)
    for path in paths:
        prune_file(path, cache)
    return 0


if __name__ == "__main__":
    sys.exit(main())
