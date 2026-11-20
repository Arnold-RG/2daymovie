#!/usr/bin/env python3
"""Rebuild data/catalog.json from the channel list in scripts/channels.json.

Uses yt-dlp only (no API key). Steps:
  1. resolve channels listed by name only (exact-name channel search; ambiguous
     or missing names are skipped and recorded in scripts/channel_resolution.json)
  2. list each channel's uploads (flat playlist, no per-video requests)
  3. pick long-form candidates per content type (full movies >= 40 min, real
     episodes, full cartoons, full documentaries)
  4. verify every candidate individually: public, not live, not age-restricted,
     playable_in_embed == True
  5. write data/catalog.json (public: no channel names/links/ids) and
     data/catalog_sources.json (internal: video id -> source channel id)

Usage:
  pip install -r scripts/requirements.txt
  python scripts/build_catalog.py            # full refresh
  python scripts/build_catalog.py --per-channel 6 --workers 6
Intermediate results are cached in scripts/.cache/ so reruns resume.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANNELS = ROOT / "scripts" / "channels.json"
RESOLUTION = ROOT / "scripts" / "channel_resolution.json"
CACHE = ROOT / "scripts" / ".cache"
OUT = ROOT / "data" / "catalog.json"
SOURCES = ROOT / "data" / "catalog_sources.json"
TRAILERS = ROOT / "data" / "trailers.json"

YTDLP = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--ignore-config"]

# Section / row layout (content types, never channel names)
SECTIONS = [
    ("movies", "Movies"),
    ("series", "Series"),
    ("kids", "Kids"),
    ("cartoons", "Cartoons"),
    ("ai", "AI Animation / Manhwa"),
    ("wildlife", "Wildlife & Nature"),
]

PRESCHOOL = {
    "Peppa Pig", "Bluey", "PBS KIDS", "Pocoyo", "Morphle TV", "PAW Patrol", "BabyBus",
    "CoComelon", "Pinkfong", "Super Simple Songs", "CBeebies", "Sesame Street",
    "Sesame Street Classics", "Teletubbies — WildBrain", "True and the Rainbow Kingdom",
    "Tayo the Little Bus", "Robocar POLI TV", "Moonbug Kids", "Sheriff Labrador — Kids Cartoon",
    "TeeniepingTV", "Tulipop — Official Channel", "LooLoo Kids", "Little Baby Bum",
    "Dave and Ava", "ChuChu TV", "Leo the Truck", "Numberblocks", "Molang", "GOGOBUS",
    "Katuri", "Bob the Train", "WildBrain Kids", "Pokémon Kids TV",
}
ASIAN_MOVIES = {"China Movie Channel ENGLISH", "Tencent Video-MOVIE", "Korean Classic Film", "Korean Film Archive"}
ANIME = {"Korean Animation", "TMS Anime", "Anime! on TMS Official Channel", "GundamInfo", "Muse Asia",
         "Ani-One Asia", "Toei Animation", "Pokémon Asia Official"}
TRAVEL = {"Drew Binsky", "Indigo Traveller", "Itchy Boots", "Eva zu Beck", "Best Ever Food Review Show",
          "4K Urban Life", "National Geographic Travel", "Journeyman Pictures", "Scenic Relaxation",
          "Amazing Places on Our Planet"}

EPISODE_RE = re.compile(r"\b(ep|eps|episode|episodes|épisode|season|saison|s\d{1,2}\s?e\d{1,3}|igice|agace)\b\.?\s*\d*", re.I)
EP_NUM_RE = re.compile(r"\b(ep|episode|épisode|igice|agace)\s*\.?\s*(\d{1,3})\b", re.I)
JUNK_RE = re.compile(r"\b(trailer|teaser|promo|shorts?|live stream|behind the scenes|bts|interview|reaction|announcement|preview|clip)\b", re.I)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def name_variants(name: str) -> list[str]:
    parts = {name}
    for sep in (" — ", " / ", " - "):
        if sep in name:
            parts.update(p.strip() for p in name.split(sep))
    return [p for p in parts if p]


def run_json(args: list[str], timeout: int = 120) -> dict:
    d = _run_json(args, timeout)
    return d if isinstance(d, dict) else {"_error": ["empty response"]}


def _run_json(args: list[str], timeout: int = 120):
    for attempt in range(3):
        try:
            p = subprocess.run(YTDLP + args, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            continue
        out = p.stdout.strip()
        if out:
            try:
                return json.loads(out.splitlines()[-1]) if args[0] == "-j" else json.loads(out)
            except json.JSONDecodeError:
                pass
        if "not a bot" in p.stderr:
            time.sleep(20 * (attempt + 1))
            continue
        return {"_error": (p.stderr or "").strip().splitlines()[-1:] }
    return {"_error": ["retries exhausted"]}


def cache_get(kind: str, key: str):
    f = CACHE / kind / (re.sub(r"[^A-Za-z0-9_.-]", "_", key) + ".json")
    return json.loads(f.read_text()) if f.exists() else None


def cache_put(kind: str, key: str, value) -> None:
    d = CACHE / kind
    d.mkdir(parents=True, exist_ok=True)
    (d / (re.sub(r"[^A-Za-z0-9_.-]", "_", key) + ".json")).write_text(json.dumps(value))


# ---------- 1. resolve ----------
def resolve(ch: dict) -> dict:
    if ch.get("url"):
        return {"status": "listed", "url": ch["url"]}
    cached = cache_get("resolve", ch["name"])
    if cached:
        return cached
    wanted = {norm(v) for v in name_variants(ch["name"])}
    query = re.sub(r"[—/]", " ", ch["name"])
    d = run_json(["--flat-playlist", "-J", "--playlist-end", "10",
                  "https://www.youtube.com/results?search_query=" + query.replace(" ", "+") + "&sp=EgIQAg%253D%253D"])
    hits = [e for e in (d.get("entries") or []) if norm(e.get("channel") or e.get("title") or "") in wanted]
    if not hits:
        res = {"status": "unresolved", "reason": "no channel with this exact name"}
    else:
        hits.sort(key=lambda e: (bool(e.get("channel_is_verified")), e.get("channel_follower_count") or 0), reverse=True)
        best = hits[0]
        res = {"status": "resolved", "url": f"https://www.youtube.com/channel/{best['channel_id']}",
               "matched_name": best.get("channel"), "followers": best.get("channel_follower_count"),
               "verified": bool(best.get("channel_is_verified"))}
    cache_put("resolve", ch["name"], res)
    return res


MIN_FOLLOWERS = 1000


def confident(res: dict) -> dict:
    """Only keep a name-search match we are confident is the intended channel."""
    if res.get("status") != "resolved":
        return res
    matched = res.get("matched_name") or ""
    if (res.get("followers") or 0) < MIN_FOLLOWERS:
        return {**res, "status": "rejected", "url": None,
                "reason": f"only a tiny channel ({res.get('followers')} subscribers) has this name"}
    if re.search(r"[^\x00-\u024F\s\-—|&'’!.,:()+]", matched):
        return {**res, "status": "rejected", "url": None,
                "reason": "only a regional-language variant of this name was found"}
    return res


# ---------- 2. list uploads ----------
def list_uploads(url: str, limit: int) -> dict:
    cached = cache_get("uploads", url)
    if cached:
        return cached
    base = url.rstrip("/")
    d = run_json(["--flat-playlist", "-J", "--playlist-end", str(limit), base + "/videos"], timeout=180)
    res = {"channel_id": d.get("channel_id") or d.get("id"),
           "entries": [{"id": e["id"], "title": e.get("title") or "", "duration": e.get("duration"),
                        "views": e.get("view_count") or 0}
                       for e in (d.get("entries") or []) if e.get("id") and e.get("duration")],
           "error": d.get("_error")}
    cache_put("uploads", url, res)
    return res


# ---------- 3. classify ----------
def classify(ch: dict, title: str, dur: int):
    g, name = ch["group"], ch["name"]
    episodic = bool(EPISODE_RE.search(title))
    if JUNK_RE.search(title):
        return None
    if g in ("nollywood", "rwanda", "french", "bollywood"):
        row = {"nollywood": "Nollywood", "rwanda": "Rwanda / Kinyarwanda", "french": "French",
               "bollywood": "Bollywood"}[g]
        if episodic and dur >= 900:
            return ("series", {"nollywood": "Nollywood Series", "rwanda": "Rwandan Series",
                               "french": "French Series", "bollywood": "Indian Series"}[g])
        if g == "rwanda" and "SERIES" in name.upper() and dur >= 900:
            return ("series", "Rwandan Series")
        return ("movies", row) if dur >= 2400 else None
    if g == "international":
        if name == "Family Central":
            return ("cartoons", "Family Cartoons") if dur >= 600 else None
        if name == "FilmRise Television":
            return ("series", "TV Series") if dur >= 1200 else None
        return ("movies", "International") if dur >= 2400 else None
    if g == "asian":
        if name in ANIME:
            return ("series", "Anime") if dur >= 900 else None
        if name in ASIAN_MOVIES:
            return ("movies", "Asian Cinema") if dur >= 2400 else None
        if episodic and dur >= 1200:
            return ("series", "Asian Dramas")
        if dur >= 4800 and not episodic:
            return ("movies", "Asian Cinema")
        return None
    if g == "kids":
        if dur < 420:
            return None
        return ("kids", "Preschool & Little Ones") if name in PRESCHOOL else ("cartoons", "Cartoon Favourites")
    if g == "ai":
        if dur < 480:
            return None
        return ("ai", "Manhwa Recaps") if "manhwa" in name.lower() or "recap" in name.lower() or "manhoryn" in name.lower() or "yunowha" in name.lower() else ("ai", "AI Animation & Fantasy")
    if g == "wildlife":
        if dur < 1200:
            return None
        return ("wildlife", "Travel & Adventure") if name in TRAVEL else ("wildlife", "Wildlife Documentaries")
    return None


# ---------- 4. verify ----------
def verify(vid: str) -> dict:
    cached = cache_get("verify", vid)
    if cached and (cached.get("ok") or cached.get("retried")):
        return cached
    url = f"https://www.youtube.com/watch?v={vid}"
    d = run_json(["-j", "--skip-download", url], timeout=90)
    if "_error" in d and "not available" in " ".join(d["_error"]):
        # made-for-kids and some music-licensed uploads only answer the embedded
        # player client; that answer is exactly what the site needs to know
        d = run_json(["-j", "--skip-download", "--ignore-no-formats-error",
                      "--extractor-args", "youtube:player_client=web_embedded", url], timeout=90)
    res = {"ok": False}
    if "_error" in d:
        res["reason"] = " ".join(d["_error"])[:200] or "unavailable"
    else:
        res = {
            "ok": bool(d.get("playable_in_embed")) and (d.get("age_limit") or 0) == 0
            and d.get("availability") in ("public", "unlisted", None)
            and d.get("live_status") in ("not_live", "was_live", None),
            "title": d.get("title"), "duration": d.get("duration"),
            "upload_date": d.get("upload_date"), "channel_id": d.get("channel_id"),
            "channel": d.get("channel"), "uploader_id": d.get("uploader_id"),
            "embed": d.get("playable_in_embed"), "age_limit": d.get("age_limit"),
            "availability": d.get("availability"), "live_status": d.get("live_status"),
        }
        if not res["ok"]:
            res["reason"] = "not embeddable/age-restricted/private/live"
    res["retried"] = True
    cache_put("verify", vid, res)
    return res


# ---------- 5. titles ----------
BRANDY = re.compile(r"\b(tv|movies?|films?|studios?|entertainment|channel|recaps?|cinema|official|flix|plus)\b", re.I)


def clean_title(title: str, banned: list[str]) -> str:
    """Real title with hashtags, @handles and channel-name tags removed."""
    t = re.sub(r"#\S+", " ", title)
    t = re.sub(r"@\S+", " ", t)
    banned = [b for b in banned if len(b) >= 4]
    keys = {norm(b) for b in banned}
    keys |= {k + suf for k in list(keys) for suf in ("official", "tv", "channel", "movies")}
    # drop separator segments that are only the channel name ("Title | Some Channel TV")
    parts = re.split(r"\s*[|｜•]\s*", t)
    if len(parts) > 1:
        kept = [parts[0]] + [p for p in parts[1:] if norm(p) not in keys and norm(p)]
        t = " | ".join(kept)
    # brand-like channel names ("X TV", "Y Movies") are removed anywhere in the title;
    # show-name channels ("Peppa Pig", "Mr Bean") stay because they are the show's title
    for b in sorted(banned, key=len, reverse=True):
        if BRANDY.search(b):
            t = re.sub(r"[\[(]?\s*" + re.escape(b) + r"\s*[\])]?", " ", t, flags=re.I)
    t = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]", " ", t)
    t = re.sub(r"\(\s*\)|\[\s*\]", " ", t)
    t = re.sub(r"(\s*[|｜:–—,-]\s*){2,}", " | ", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" -|｜:–—,.")
    return t or title.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-channel", type=int, default=8)
    ap.add_argument("--scan", type=int, default=90, help="uploads scanned per channel")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    channels = json.loads(CHANNELS.read_text())
    with cf.ThreadPoolExecutor(args.workers) as ex:
        resolutions = [confident(r) for r in ex.map(resolve, channels)]
    RESOLUTION.write_text(json.dumps(
        [{"name": c["name"], "group": c["group"], **r} for c, r in zip(channels, resolutions)],
        indent=1, ensure_ascii=False) + "\n")
    active = [(c, r["url"]) for c, r in zip(channels, resolutions) if r.get("url")]
    print(f"channels: {len(channels)} listed, {len(active)} usable", file=sys.stderr)

    with cf.ThreadPoolExecutor(args.workers) as ex:
        uploads = list(ex.map(lambda cu: list_uploads(cu[1], args.scan), active))

    candidates = []  # (channel, entry, section, row)
    seen = set()
    channel_ids = {}
    for (ch, _), up in zip(active, uploads):
        if up.get("channel_id"):
            channel_ids[ch["name"]] = up["channel_id"]
        picks = []
        for e in sorted(up["entries"], key=lambda e: e["views"], reverse=True):
            if e["id"] in seen:
                continue
            cls = classify(ch, e["title"], int(e["duration"] or 0))
            if cls:
                picks.append((ch, e, *cls))
                seen.add(e["id"])
            if len(picks) >= args.per_channel + 3:  # spare in case some fail verification
                break
        candidates.extend(picks)
    print(f"candidates: {len(candidates)}", file=sys.stderr)

    with cf.ThreadPoolExecutor(args.workers) as ex:
        checks = list(ex.map(lambda c: verify(c[1]["id"]), candidates))

    trailer_ids = set()
    if TRAILERS.exists():
        trailer_ids = {t["youtube_id"] for t in json.loads(TRAILERS.read_text())["items"]}

    per_channel: dict[str, int] = {}
    items, sources, skipped = [], {}, []
    for (ch, e, section, row), v in zip(candidates, checks):
        if not v.get("ok"):
            skipped.append({"id": e["id"], "reason": v.get("reason")})
            continue
        if e["id"] in trailer_ids or per_channel.get(ch["name"], 0) >= args.per_channel:
            continue
        expected = channel_ids.get(ch["name"])
        if expected and v.get("channel_id") and v["channel_id"] != expected:
            skipped.append({"id": e["id"], "reason": "uploaded by a different channel"})
            continue
        per_channel[ch["name"]] = per_channel.get(ch["name"], 0) + 1
        banned = name_variants(ch["name"]) + [v.get("channel") or "", (v.get("uploader_id") or "").lstrip("@")]
        items.append({
            "id": e["id"],
            "title": clean_title(v["title"], banned),
            "duration": int(v["duration"]),
            "year": int(v["upload_date"][:4]) if v.get("upload_date") else None,
            "section": section,
            "row": row,
        })
        sources[e["id"]] = v.get("channel_id")

    # Interleave so one source never dominates the start of a row
    by_row: dict[tuple, list] = {}
    for it in items:
        by_row.setdefault((it["section"], it["row"]), []).append(it)
    ordered = []
    for key, lst in by_row.items():
        buckets: dict[str, list] = {}
        for it in lst:
            buckets.setdefault(sources[it["id"]], []).append(it)
        while any(buckets.values()):
            for b in buckets.values():
                if b:
                    ordered.append(b.pop(0))
    # Public schema: { id, title, type, genres, duration, thumbnail }. "type" is the
    # section (movies, series, kids, cartoons, ai, wildlife); genres[0] is the row.
    catalog = {
        "generated": time.strftime("%Y-%m-%d"),
        "items": [
            {"id": it["id"], "title": it["title"], "type": it["section"], "genres": [it["row"]],
             "duration": it["duration"], "thumbnail": f"https://i.ytimg.com/vi/{it['id']}/mqdefault.jpg"}
            for it in ordered
        ],
    }
    OUT.write_text(json.dumps(catalog, indent=1, ensure_ascii=False) + "\n")
    used = {sources[i["id"]] for i in ordered}
    SOURCES.write_text(json.dumps({
        "note": "internal only, never rendered: video id -> source channel id",
        "videos": sources,
        "channels_with_videos": sorted(n for n, cid in channel_ids.items() if cid in used),
        "channels_without_videos": sorted(c["name"] for c in channels if channel_ids.get(c["name"]) not in used),
        "skipped": skipped,
    }, indent=1, ensure_ascii=False) + "\n")
    counts = {}
    for it in ordered:
        counts[it["section"]] = counts.get(it["section"], 0) + 1
    print(json.dumps(counts), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
