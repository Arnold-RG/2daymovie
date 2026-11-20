#!/usr/bin/env python3
"""Rebuild or refine data/catalog.json from the channel list in scripts/channels.json.

Uses yt-dlp only (no API key). Steps:
  1. resolve channels listed by name only (exact-name channel search; ambiguous
     or missing names are skipped and recorded in scripts/channel_resolution.json)
  2. list each channel's uploads (flat playlist, no per-video requests)
  3. pick long-form candidates per content type (full movies >= 20 min, real
     episodes, full cartoons, full documentaries)
  4. verify every candidate individually: public, not live, not age-restricted,
     playable_in_embed == True, and YouTube oEmbed HTTP 200
  5. write data/catalog.json (public: no channel names/links/ids) and
     data/catalog_sources.json (internal: video id -> source channel id)

Made-for-kids uploads often fail yt-dlp's default client but answer both oEmbed
and the embedded-player client; verify() retries those automatically.

Usage:
  pip install -r scripts/requirements.txt
  python scripts/build_catalog.py            # full refresh
  python scripts/build_catalog.py --per-channel 6 --workers 6
  python scripts/build_catalog.py --refine   # verify the existing catalog, drop
                                             # failures, and fill thin kids/cartoons rows
  python scripts/build_catalog.py --enrich-genres
                                             # append real genres to movies/series that
                                             # only have a row name, using yt-dlp metadata
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
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CHANNELS = ROOT / "scripts" / "channels.json"
RESOLUTION = ROOT / "scripts" / "channel_resolution.json"
CACHE = ROOT / "scripts" / ".cache"
OUT = ROOT / "data" / "catalog.json"
SOURCES = ROOT / "data" / "catalog_sources.json"
TRAILERS = ROOT / "data" / "trailers.json"
DROPPED = ROOT / "data" / "catalog_dropped.json"
REVIEW = ROOT / "data" / "catalog_review.json"

YTDLP = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--ignore-config"]
WARSAW = ZoneInfo("Europe/Warsaw")

# Section / row layout (content types, never channel names)
SECTIONS = [
    ("movies", "Movies"),
    ("series", "Series"),
    ("kids", "Kids"),
    ("cartoons", "Cartoons"),
    ("ai", "AI Animation / Manhwa"),
    ("wildlife", "Wildlife & Nature"),
]
SECTION_ORDER = {name: i for i, (name, _) in enumerate(SECTIONS)}

# Real genres that may follow genres[0] (the row name the site uses for shelves).
REAL_GENRES = [
    "Drama", "Action", "Adventure", "Sci-Fi", "Musical", "Horror", "Comedy",
    "Romance", "Thriller", "Documentary", "Fantasy", "Family", "Animation",
    "Crime", "Mystery", "History", "Nature",
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
JUNK_RE = re.compile(r"\b(trailer|teaser|promo|shorts?|live stream|behind the scenes|bts|interview|reaction|announcement|preview|clips?)\b", re.I)

# Minimum full-length durations: 20 min for movies and animation, 8 min for
# episodes, kids and wildlife.
MIN_SECONDS = {
    "movies": 20 * 60,
    "cartoons": 20 * 60,
    "ai": 20 * 60,
    "series": 8 * 60,
    "kids": 8 * 60,
    "wildlife": 8 * 60,
}

GENRE_RULES = [
    ("Sci-Fi", re.compile(r"\b(sci[-\s]?fi|science fiction|space opera|alien|android|cyborg|dystopia|futuristic|time travel)\b", re.I)),
    ("Horror", re.compile(r"\b(horror|haunted|ghost|zombie|demon|vampire|exorcism|nightmare)\b", re.I)),
    ("Musical", re.compile(r"\b(musical|nursery rhyme|sing[- ]?along|lullaby|karaoke)\b", re.I)),
    ("Romance", re.compile(r"\b(romance|romantic|love story|one sided love|wedding|marriage|husband|wife)\b", re.I)),
    ("Comedy", re.compile(r"\b(comedy|comed(y|ic)|funny|hilarious|slapstick)\b", re.I)),
    ("Crime", re.compile(r"\b(crime|heist|mafia|gangster|assassin)\b", re.I)),
    ("Mystery", re.compile(r"\b(mystery|detective|whodunnit|whodunit)\b", re.I)),
    ("Thriller", re.compile(r"\b(thriller|suspense)\b", re.I)),
    ("Action", re.compile(r"\b(action|fight|fighter|battle|war |soldier|mission|martial arts|kung fu)\b", re.I)),
    ("Adventure", re.compile(r"\b(adventure|quest|journey|expedition|road trip)\b", re.I)),
    ("Fantasy", re.compile(r"\b(fantasy|magical|wizard|dragon|enchanted|ghibli|manhwa|isekai)\b", re.I)),
    ("History", re.compile(r"\b(history|historical|ancient|empire|kingdom|medieval)\b", re.I)),
    ("Documentary", re.compile(r"\b(documentary|documentaries|true story|investigat)\b", re.I)),
    ("Nature", re.compile(r"\b(wildlife|nature|animal|ocean|planet earth|safari|rainforest)\b", re.I)),
    ("Animation", re.compile(r"\b(animation|animated|cartoon|anime|cgi)\b", re.I)),
    ("Family", re.compile(r"\b(family|preschool|children|kids)\b", re.I)),
    ("Drama", re.compile(r"\b(drama|melodrama|faith drama)\b", re.I)),
]


def load_channels() -> list[dict]:
    """scripts/channels.json is local-only (gitignored) so channel names never ship."""
    if not CHANNELS.exists():
        raise SystemExit(f"{CHANNELS} not found. It is not tracked in git; copy the private "
                         "channel list there (see README) and run again.")
    return json.loads(CHANNELS.read_text())


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


def _transient_oembed(res: dict | None) -> bool:
    if not res:
        return True
    reason = str(res.get("reason") or "")
    return (not res.get("ok")) and (res.get("status") in (None, 0) or "URLError" in reason or "Timeout" in reason)


def oembed(vid: str) -> dict:
    """YouTube oEmbed: HTTP 200 means the video is embeddable.

    Transient network errors are not treated as a final 'not embeddable' result.
    """
    cached = cache_get("oembed", vid)
    if cached and cached.get("retried") and not _transient_oembed(cached):
        return cached
    url = f"https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v={vid}"
    req = urllib.request.Request(url, headers={"User-Agent": "2DayMovieCatalog/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            res = {"ok": resp.status == 200, "status": resp.status, "title": payload.get("title"), "retried": True}
    except urllib.error.HTTPError as e:
        res = {"ok": False, "status": e.code, "reason": f"oembed HTTP {e.code}", "retried": True}
    except Exception as e:
        res = {"ok": False, "status": 0, "reason": f"oembed error: {type(e).__name__}", "retried": False}
    cache_put("oembed", vid, res)
    return res


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
            # Live-action family films belong in Movies, not the Cartoons row.
            return ("movies", "Family") if dur >= 20 * 60 else None
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
        if name == "Mr Bean" and re.search(r"\blive action\b", title, re.I):
            return ("movies", "Comedy") if dur >= 20 * 60 else None
        if name in PRESCHOOL:
            return ("kids", "Preschool & Little Ones") if dur >= MIN_SECONDS["kids"] else None
        return ("cartoons", "Cartoon Favourites") if dur >= MIN_SECONDS["cartoons"] else None
    if g == "ai":
        if dur < MIN_SECONDS["ai"]:
            return None
        return ("ai", "Manhwa Recaps") if "manhwa" in name.lower() or "recap" in name.lower() or "manhoryn" in name.lower() or "yunowha" in name.lower() else ("ai", "AI Animation & Fantasy")
    if g == "wildlife":
        if dur < 1200:
            return None
        return ("wildlife", "Travel & Adventure") if name in TRAVEL else ("wildlife", "Wildlife Documentaries")
    return None


def extra_genres(section: str, title: str) -> list[str]:
    """Real genres from the title only. Never invent a default."""
    found: list[str] = []
    for genre, pat in GENRE_RULES:
        if pat.search(title) and genre not in found:
            # "kids" in a wildlife title should not force a Family shelf item.
            if genre == "Family" and section in {"wildlife", "ai"}:
                continue
            if genre == "Horror" and section in {"kids", "cartoons"}:
                continue
            found.append(genre)
    if section == "kids":
        for g in ("Family", "Animation"):
            if g not in found:
                found.append(g)
    elif section == "cartoons":
        for g in ("Animation", "Family"):
            if g not in found:
                found.append(g)
    elif section == "wildlife":
        for g in ("Nature", "Documentary"):
            if g not in found:
                found.append(g)
    elif section == "ai":
        if "Animation" not in found:
            found.append("Animation")
    return found


def genres_for(section: str, row: str, title: str) -> list[str]:
    """genres[0] is the on-site row name; further entries are real genres."""
    extras = [g for g in extra_genres(section, title) if g != row]
    return [row] + extras


# ---------- 4. verify ----------
def _yt_metadata(url: str, embedded: bool) -> dict:
    args = ["-j", "--skip-download"]
    if embedded:
        args += ["--ignore-no-formats-error", "--extractor-args", "youtube:player_client=web_embedded"]
    return run_json(args + [url], timeout=90)


def _verify_result(d: dict, embedded: bool, oembed_res: dict) -> dict:
    res: dict
    if "_error" in d:
        res = {"ok": False, "reason": " ".join(d["_error"])[:200] or "unavailable"}
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
    if not oembed_res.get("ok"):
        res["ok"] = False
        res["reason"] = oembed_res.get("reason") or f"oembed HTTP {oembed_res.get('status')}"
    else:
        res.setdefault("title", oembed_res.get("title"))
    res["oembed_ok"] = bool(oembed_res.get("ok"))
    res["embedded_tried"] = embedded
    res["retried"] = True
    return res


def verify(vid: str) -> dict:
    """Public, embeddable, not live. Retries made-for-kids with the embedded client.

    Stale cache entries that failed the default client without an embedded retry
    (no 'retried' / 'embedded_tried' flag) are fetched again. oEmbed HTTP 200 is
    required in addition to playable_in_embed.
    """
    oembed_res = oembed(vid)
    cached = cache_get("verify", vid)
    if cached and cached.get("ok") and cached.get("retried"):
        if cached.get("oembed_ok") is None:
            cached = {**cached, "oembed_ok": oembed_res.get("ok")}
            if not oembed_res.get("ok"):
                cached["ok"] = False
                cached["reason"] = oembed_res.get("reason") or "oembed failed"
            cache_put("verify", vid, cached)
        elif not cached.get("oembed_ok") or not oembed_res.get("ok"):
            cached = {**cached, "ok": False, "oembed_ok": False,
                      "reason": oembed_res.get("reason") or cached.get("reason") or "oembed failed"}
            cache_put("verify", vid, cached)
        return cached
    # A previous default-client failure without an embedded retry must be redone.
    if cached and not cached.get("ok") and cached.get("embedded_tried") and cached.get("retried"):
        if cached.get("oembed_ok") is None:
            cached["oembed_ok"] = oembed_res.get("ok")
            if not oembed_res.get("ok"):
                cache_put("verify", vid, cached)
        return cached

    url = f"https://www.youtube.com/watch?v={vid}"
    d = _yt_metadata(url, embedded=False)
    used_embedded = False
    need_embedded = "_error" in d and "not available" in " ".join(d["_error"])
    if not need_embedded and not d.get("playable_in_embed") and oembed_res.get("ok"):
        need_embedded = True
    if need_embedded:
        d = _yt_metadata(url, embedded=True)
        used_embedded = True
    res = _verify_result(d, used_embedded, oembed_res)
    cache_put("verify", vid, res)
    return res


# ---------- 5. titles ----------
BRANDY = re.compile(r"\b(tv|movies?|films?|studios?|entertainment|channel|recaps?|cinema|official|flix|plus)\b", re.I)


def _segment_is_channel(part: str, keys: set[str], banned: list[str]) -> bool:
    n = norm(part)
    if not n:
        return True
    if n in keys or n in {"official", "officialchannel", "officialtrailer"}:
        return True
    seg_words = re.findall(r"[a-z0-9]+", part.lower())
    if seg_words and seg_words[-1] in {"4k", "uhd", "hd"}:
        seg_words = seg_words[:-1]
    for b in banned:
        bn = norm(b)
        if len(bn) >= 6 and bn in n:
            return True
        ch_words = re.findall(r"[a-z0-9]+", b.lower())
        if len(seg_words) >= 2 and ch_words[:len(seg_words)] == seg_words:
            return True
    return False


def clean_title(title: str, banned: list[str]) -> str:
    """Real title with hashtags, @handles and channel-name tags removed."""
    t = re.sub(r"#\S+", " ", title)
    t = re.sub(r"@\S+", " ", t)
    banned = [b for b in banned if len(b) >= 4]
    keys = {norm(b) for b in banned}
    keys |= {k + suf for k in list(keys) for suf in ("official", "tv", "channel", "movies", "4k")}
    # drop separator segments that are the channel name ("Title | Some Channel TV"),
    # a lone "Official" tag, or a bracket tag like "[Amazing Places 4K]".
    # Show-name channels stay when they are part of the main title segment.
    parts = re.split(r"\s*[|｜•]\s*", t)
    if len(parts) > 1:
        kept = [parts[0]] + [p for p in parts[1:] if not _segment_is_channel(p, keys, banned)]
        t = " | ".join(kept)
    t = re.sub(r"\[\s*([^\]]+?)\s*\]", lambda m: " " if _segment_is_channel(m.group(1), keys, banned) else m.group(0), t)
    # brand-like channel names ("X TV", "Y Movies") are removed anywhere in the title;
    # show-name channels ("Peppa Pig", "Mr Bean") stay because they are the show's title
    for b in sorted(banned, key=len, reverse=True):
        if BRANDY.search(b):
            t = re.sub(r"[\[(]?\s*" + re.escape(b) + r"\s*[\])]?", " ", t, flags=re.I)
        t = re.sub(
            r"[\s\-–—:|•,]+" + re.escape(b) + r"(?:\s+film(?:s)?(?:\s+with\s+calming\s+music)?)?\s*$",
            "",
            t,
            flags=re.I,
        )
    t = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]", " ", t)
    t = re.sub(r"\(\s*\)|\[\s*\]", " ", t)
    t = re.sub(r"(\s*[|｜:–—,-]\s*){2,}", " | ", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" -|｜:–—,.")
    return t.strip() or title.strip()


def now_iso() -> str:
    return datetime.now(WARSAW).isoformat(timespec="seconds")


def trailer_ids() -> set[str]:
    if not TRAILERS.exists():
        return set()
    data = json.loads(TRAILERS.read_text())
    items = data["items"] if isinstance(data, dict) else data
    return {t.get("youtube_id") or t.get("id") for t in items if t.get("youtube_id") or t.get("id")}


def write_catalog(items: list[dict], sources: dict, channels: list[dict], channel_ids: dict, skipped: list) -> None:
    # Dedupe by id, keep first; sort by section order, then row, then title.
    seen = set()
    unique = []
    for it in items:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        unique.append(it)
    unique.sort(key=lambda it: (SECTION_ORDER.get(it["type"], 99), (it["genres"][0] if it.get("genres") else ""), it["title"].casefold(), it["id"]))
    catalog = {
        "generated": now_iso(),
        "items": [
            {
                "id": it["id"],
                "title": it["title"],
                "type": it["type"],
                "genres": it["genres"],
                "duration": int(it["duration"]),
                "thumbnail": it.get("thumbnail") or f"https://i.ytimg.com/vi/{it['id']}/hqdefault.jpg",
            }
            for it in unique
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(catalog, indent=1, ensure_ascii=False) + "\n")
    used = {sources[i["id"]] for i in unique if i["id"] in sources}
    name_of = {}
    for c in channels:
        cid = channel_ids.get(c["name"])
        if cid:
            name_of[cid] = c["name"]
    SOURCES.write_text(json.dumps({
        "note": "internal only, never rendered: video id -> source channel id",
        "videos": {k: v for k, v in sources.items() if k in seen},
        "channels_with_videos": sorted({name_of[s] for s in used if s in name_of} | {n for n, cid in channel_ids.items() if cid in used and n}),
        "channels_without_videos": sorted(c["name"] for c in channels if channel_ids.get(c["name"]) not in used),
        "skipped": skipped,
    }, indent=1, ensure_ascii=False) + "\n")
    counts = {}
    for it in unique:
        counts[it["type"]] = counts.get(it["type"], 0) + 1
    print(json.dumps({"generated": catalog["generated"], "total": len(unique), "counts": counts}), file=sys.stderr)


def load_resolution() -> dict:
    if not RESOLUTION.exists():
        return {}
    return {r["name"]: r for r in json.loads(RESOLUTION.read_text())}


def active_channels(channels: list[dict]) -> list[tuple[dict, str]]:
    reso = load_resolution()
    active = []
    for c in channels:
        url = c.get("url") or (reso.get(c["name"]) or {}).get("url")
        if url:
            active.append((c, url))
    return active


def duration_ok(section: str, duration: int) -> bool:
    return int(duration or 0) >= MIN_SECONDS.get(section, 20 * 60)


# ---------- refine: verify existing + fill thin kids/cartoon rows ----------
def refine(args) -> int:
    channels = load_channels()
    catalog = json.loads(OUT.read_text())
    existing = catalog["items"] if isinstance(catalog, dict) else catalog
    sources = {}
    skipped_prev = []
    if SOURCES.exists():
        src = json.loads(SOURCES.read_text())
        sources = dict(src.get("videos") or {})
        skipped_prev = list(src.get("skipped") or [])
    cid_to_name = {}
    name_to_ch = {c["name"]: c for c in channels}
    for r in load_resolution().values():
        url = r.get("url") or ""
        if "/channel/" in url:
            cid_to_name[url.rstrip("/").split("/")[-1]] = r["name"]
    for vid, cid in sources.items():
        cached = cache_get("verify", vid) or {}
        if cached.get("channel_id") and cached.get("channel"):
            cid_to_name.setdefault(cached["channel_id"], cached["channel"])

    print(f"refine: verifying {len(existing)} existing items", file=sys.stderr)
    with cf.ThreadPoolExecutor(args.workers) as ex:
        checks = list(ex.map(lambda it: (it, verify(it["id"])), existing))

    dropped = []
    kept = []
    review = []
    for it, v in checks:
        reasons = []
        raw_title = (v.get("title") or it["title"] or "").strip()
        if not v.get("ok"):
            reasons.append(v.get("reason") or "verification failed")
        duration = int(v["duration"] if v.get("duration") else it["duration"])
        section = it["type"]
        # Reclassify live-action family films and Mr Bean live-action out of Cartoons.
        title_l = raw_title.lower()
        ch_name = cid_to_name.get(sources.get(it["id"]), "")
        if section == "cartoons" and (
            "family central" in (ch_name or "").lower()
            or "faith drama" in title_l
            or (re.search(r"\bfull (adventure|comedy|faith drama )?movie\b", title_l) and "animation" not in title_l)
        ):
            section = "movies"
        if section == "cartoons" and re.search(r"\blive action\b", title_l):
            section = "movies"
        if JUNK_RE.search(raw_title):
            reasons.append("junk title (trailer/teaser/clip/shorts)")
        if not duration_ok(section, duration):
            reasons.append(f"too short ({duration}s < {MIN_SECONDS.get(section, 1200)}s for {section})")
        if it["id"] in trailer_ids():
            reasons.append("listed as a trailer")
        if reasons:
            dropped.append({"id": it["id"], "title": raw_title or it["title"], "from": it["type"], "reasons": reasons})
            continue
        banned = []
        for c in channels:
            banned.extend(name_variants(c["name"]))
        if ch_name:
            banned += [ch_name, (v.get("uploader_id") or "").lstrip("@")]
        # Keep a careful row name in genres[0]. After a reclassification, pick a
        # row that already exists in that section rather than inventing a channel name.
        if section == it["type"]:
            row = (it.get("genres") or ["More to watch"])[0]
            if row in {"Family Cartoons"} and section == "movies":
                row = "Family"
        else:
            row = "Family" if section == "movies" and "live action" not in title_l else (
                "Comedy" if section == "movies" else (it.get("genres") or ["More to watch"])[0]
            )
            if section == "movies" and re.search(r"\blive action\b", title_l):
                row = "Comedy"
            elif section == "movies":
                row = "Family"
        title = clean_title(raw_title, banned) if banned else clean_title(raw_title, [])
        genres = genres_for(section, row, raw_title)
        if len(genres) == 1 and section in {"movies", "series"}:
            review.append({"id": it["id"], "title": title, "type": section, "reason": "no real genre keywords in title"})
        kept.append({
            "id": it["id"],
            "title": title,
            "type": section,
            "genres": genres,
            "duration": duration,
            "thumbnail": f"https://i.ytimg.com/vi/{it['id']}/hqdefault.jpg",
        })

    print(f"refine: kept {len(kept)}, dropped {len(dropped)}", file=sys.stderr)
    before_fill = {s: 0 for s, _ in SECTIONS}
    for it in kept:
        before_fill[it["type"]] = before_fill.get(it["type"], 0) + 1
    print(f"refine: after verify/reclassify {json.dumps(before_fill)}", file=sys.stderr)

    added, fill_skipped, more_sources, channel_ids = fill_kids_cartoons(args, channels, kept)
    kept.extend(added)
    skipped = skipped_prev + [{"id": d["id"], "reason": "; ".join(d["reasons"])} for d in dropped] + fill_skipped
    sources.update(more_sources)

    DROPPED.write_text(json.dumps({"dropped": dropped, "added": [
        {"id": a["id"], "title": a["title"], "type": a["type"]} for a in added
    ]}, indent=1, ensure_ascii=False) + "\n")
    REVIEW.write_text(json.dumps(review, indent=1, ensure_ascii=False) + "\n")
    write_catalog(kept, sources, channels, channel_ids, skipped)
    print(f"refine: added {len(added)} kids/cartoon titles; dropped log {DROPPED}", file=sys.stderr)
    return 0


def fill_kids_cartoons(args, channels: list[dict], already: list[dict]):
    """Pick more kids and cartoon titles from the kids-group channels."""
    have = {it["id"] for it in already}
    counts = {"kids": sum(1 for it in already if it["type"] == "kids"),
              "cartoons": sum(1 for it in already if it["type"] == "cartoons")}
    target = {"kids": args.target, "cartoons": args.target}
    print(f"fill: kids {counts['kids']}/{target['kids']}, cartoons {counts['cartoons']}/{target['cartoons']}", file=sys.stderr)

    kids_chs = [(c, u) for c, u in active_channels(channels) if c["group"] == "kids"]
    with cf.ThreadPoolExecutor(args.workers) as ex:
        uploads = list(ex.map(lambda cu: list_uploads(cu[1], args.scan), kids_chs))

    channel_ids = {}
    # candidates grouped by section, then by channel, best first
    by_section: dict[str, dict[str, list]] = {"kids": {}, "cartoons": {}}
    for (ch, _), up in zip(kids_chs, uploads):
        if up.get("channel_id"):
            channel_ids[ch["name"]] = up["channel_id"]
        for e in sorted(up.get("entries") or [], key=lambda e: e.get("views") or 0, reverse=True):
            if e["id"] in have:
                continue
            cls = classify(ch, e.get("title") or "", int(e.get("duration") or 0))
            if not cls:
                continue
            section, row = cls
            if section not in by_section:
                continue
            by_section[section].setdefault(ch["name"], []).append((ch, e, section, row))

    added, skipped, sources = [], [], {}
    per_channel: dict[str, int] = {}
    # Verify each section on its own budget so kids candidates cannot starve cartoons.
    for section in ("kids", "cartoons"):
        if counts[section] >= target[section]:
            continue
        buckets = by_section[section]
        trimmed = {n: lst[: args.per_channel + 3] for n, lst in buckets.items()}
        queue = []
        while any(trimmed.values()):
            for n in list(trimmed):
                if trimmed[n]:
                    queue.append(trimmed[n].pop(0))
        need = max(0, target[section] - counts[section]) + 8
        queue = queue[: max(need * 3, 60)]
        print(f"fill: verifying {len(queue)} {section} candidates (have {counts[section]})", file=sys.stderr)
        with cf.ThreadPoolExecutor(args.workers) as ex:
            checks = list(ex.map(lambda c: verify(c[1]["id"]), queue))
        for (ch, e, sec, row), v in zip(queue, checks):
            if counts[sec] >= target[sec]:
                continue
            if not v.get("ok"):
                skipped.append({"id": e["id"], "reason": v.get("reason")})
                continue
            if e["id"] in have or e["id"] in trailer_ids():
                continue
            if per_channel.get(ch["name"], 0) >= args.per_channel:
                continue
            duration = int(v.get("duration") or e.get("duration") or 0)
            raw_title = v.get("title") or e.get("title") or ""
            if JUNK_RE.search(raw_title) or not duration_ok(sec, duration):
                skipped.append({"id": e["id"], "reason": "short or junk after verification"})
                continue
            expected = channel_ids.get(ch["name"])
            if expected and v.get("channel_id") and v["channel_id"] != expected:
                skipped.append({"id": e["id"], "reason": "uploaded by a different channel"})
                continue
            banned = name_variants(ch["name"]) + [v.get("channel") or "", (v.get("uploader_id") or "").lstrip("@")]
            for c in channels:
                banned.extend(name_variants(c["name"]))
            item = {
                "id": e["id"],
                "title": clean_title(raw_title, banned),
                "type": sec,
                "genres": genres_for(sec, row, raw_title),
                "duration": duration,
                "thumbnail": f"https://i.ytimg.com/vi/{e['id']}/hqdefault.jpg",
            }
            added.append(item)
            have.add(e["id"])
            sources[e["id"]] = v.get("channel_id")
            per_channel[ch["name"]] = per_channel.get(ch["name"], 0) + 1
            counts[sec] += 1

        print(f"fill: added {len(added)} (kids {counts['kids']}, cartoons {counts['cartoons']})", file=sys.stderr)
    # Include channel ids from existing sources' resolution so write_catalog can name them.
    reso = load_resolution()
    for c in channels:
        url = c.get("url") or (reso.get(c["name"]) or {}).get("url") or ""
        if "/channel/" in url:
            channel_ids.setdefault(c["name"], url.rstrip("/").split("/")[-1])
    return added, skipped, sources, channel_ids



# ---------- enrich genres from YouTube metadata (never guess) ----------
# Explicit genre labels in EN/FR/ES/ZH, used on titles, tags and plot text.
# Weaker English words (mission, journey, family, …) stay title-only so a
# channel blurb cannot stamp every film with the same genres.
STRONG_GENRE_RULES = [
    ("Sci-Fi", re.compile(r"\b(sci[-\s]?fi|science fiction|science-fiction|ciencia ficci[oó]n)\b|科幻", re.I)),
    ("Horror", re.compile(r"\b(horror|horreur|terror)\b|恐怖|haunted|zombie|exorcism", re.I)),
    ("Musical", re.compile(r"\b(musical|nursery rhyme|sing[- ]?along|lullaby|karaoke|comédie musicale)\b|歌舞", re.I)),
    ("Romance", re.compile(r"\b(romance|romantic|love story|film d['’]amour)\b|爱情|愛情", re.I)),
    ("Comedy", re.compile(r"\b(comedy|comédie|comedie|comedia|hilarious|slapstick)\b|喜剧|喜劇", re.I)),
    ("Crime", re.compile(r"\b(crime|heist|mafia|gangster|assassin|policier)\b|犯罪", re.I)),
    ("Mystery", re.compile(r"\b(mystery|mystère|misterio|detective|whodunnit|whodunit)\b|悬疑|懸疑", re.I)),
    ("Thriller", re.compile(r"\b(thriller|suspense|suspenso)\b|惊悚|驚悚", re.I)),
    ("Action", re.compile(r"\b(action|acción|accion|kung[\s-]?fu|wuxia|martial arts)\b|动作|動作|武侠|武俠|战争|戰爭", re.I)),
    ("Adventure", re.compile(r"\b(adventure|aventure|aventura)\b|冒险|冒險", re.I)),
    ("Fantasy", re.compile(r"\b(fantasy|fantastique|fantas[ií]a|wizard|enchanted)\b|奇幻|魔幻", re.I)),
    ("History", re.compile(r"\b(historical|historique|hist[oó]rico|historical drama)\b|历史|歷史", re.I)),
    ("Documentary", re.compile(r"\b(documentary|documentaire|documental|documentaries)\b|纪录片|紀錄片", re.I)),
    ("Nature", re.compile(r"\b(wildlife|planet earth|rainforest|safari)\b", re.I)),
    ("Animation", re.compile(r"\b(animation|animated|cartoon|anime|animación|dessin anim[ée])\b|动画|動畫", re.I)),
    ("Family", re.compile(r"\b(family|famille|familiar|preschool)\b|家庭", re.I)),
    ("Drama", re.compile(r"\b(drama|drame|melodrama|war drama|c[- ]?drama)\b|剧情|劇情", re.I)),
]

# YouTube's official category is only trusted when it is itself a genre name.
CATEGORY_GENRE = {"Comedy": "Comedy"}
SPAM_TAG_MARKERS = {"disney", "dreamworks", "amazon", "netflix", "hbo", "pixar", "paramount"}
TITLE_ONLY_RULES = [
    ("Action", re.compile(r"kungfu|kung-fu", re.I)),
    ("History", re.compile(r"\b(history|ancient|empire|kingdom|medieval)\b", re.I)),
    ("Comedy", re.compile(r"\bfunny\b", re.I)),
    ("Romance", re.compile(r"\b(wedding|marriage|husband|wife)\b", re.I)),
    ("Horror", re.compile(r"\b(ghost|demon|vampire|nightmare)\b", re.I)),
    ("Fantasy", re.compile(r"\b(magical|dragon|ghibli|manhwa|isekai)\b", re.I)),
    ("Documentary", re.compile(r"\btrue story\b", re.I)),
    ("Family", re.compile(r"\b(children|kids)\b", re.I)),
    ("Adventure", re.compile(r"\b(quest|expedition|road trip)\b", re.I)),
]


def plot_text(description: str) -> str:
    """Keep the plot synopsis; drop links, CTAs and channel genre dumps."""
    text = description or ""
    text = re.split(
        r"https?://|\bclick here\b|\bwatch more\b|\bsubscribe\b|\bjoin membership\b|\byoutube\.com/",
        text, maxsplit=1, flags=re.I,
    )[0]
    text = re.split(r"\n\s*genre\s*:", text, maxsplit=1, flags=re.I)[0]
    return text.strip()[:800]


def tags_are_spam(tags: list) -> bool:
    """Channel-wide SEO dumps list many genres on every video; ignore them."""
    if not tags:
        return False
    lowered = [str(t).lower() for t in tags]
    if sum(1 for m in SPAM_TAG_MARKERS if any(m in t for t in lowered)) >= 2:
        return True
    hits = {genre for genre, pat in STRONG_GENRE_RULES if any(pat.search(str(t)) for t in tags)}
    return len(hits) >= 5


def genres_from_evidence(title: str, description: str = "", tags: list | None = None,
                         categories: list | None = None, title_only: bool = False) -> list[str]:
    """Return real genres supported by the given text. Never invent a default."""
    found: list[str] = []

    def add_from(text: str, rules) -> None:
        if not text:
            return
        for genre, pat in rules:
            if genre not in found and pat.search(text):
                found.append(genre)

    add_from(title or "", STRONG_GENRE_RULES + TITLE_ONLY_RULES)
    if not title_only:
        add_from(plot_text(description), STRONG_GENRE_RULES)
        if tags and not tags_are_spam(tags):
            add_from(" | ".join(str(t) for t in tags), STRONG_GENRE_RULES)
        for cat in categories or []:
            genre = CATEGORY_GENRE.get(str(cat))
            if genre and genre not in found:
                found.append(genre)
    return [g for g in found if g in REAL_GENRES]


def fetch_meta(vid: str) -> dict:
    """yt-dlp description, tags and categories, cached in scripts/.cache/meta/."""
    cached = cache_get("meta", vid)
    if cached and cached.get("retried") and not cached.get("transient"):
        return cached
    url = f"https://www.youtube.com/watch?v={vid}"
    d = _yt_metadata(url, embedded=False)
    used_embedded = False
    err = " ".join(d.get("_error") or [])
    if "not a bot" in err.lower():
        return {"ok": False, "bot": True, "reason": err[:200], "retried": False, "transient": True}
    if "_error" in d and "not available" in err:
        d = _yt_metadata(url, embedded=True)
        used_embedded = True
        err = " ".join(d.get("_error") or [])
        if "not a bot" in err.lower():
            return {"ok": False, "bot": True, "reason": err[:200], "retried": False, "transient": True}
    if "_error" in d:
        transient = "retries exhausted" in err or "timed out" in err.lower() or not err
        res = {"ok": False, "reason": err[:200] or "unavailable", "retried": not transient,
               "transient": transient, "embedded_tried": used_embedded}
        cache_put("meta", vid, res)
        return res
    res = {
        "ok": True,
        "title": d.get("title") or "",
        "description": d.get("description") or "",
        "tags": d.get("tags") or [],
        "categories": d.get("categories") or [],
        "retried": True,
        "transient": False,
        "embedded_tried": used_embedded,
    }
    cache_put("meta", vid, res)
    return res


def _save_catalog(catalog: dict) -> None:
    catalog["generated"] = now_iso()
    OUT.write_text(json.dumps(catalog, indent=1, ensure_ascii=False) + "\n")


def enrich_genres(args) -> int:
    """Append real genres to movies/series that only have their row name.

    Requests are sequential and spaced, so a YouTube bot check can stop the
    run and keep whatever has already been tagged.
    """
    catalog = json.loads(OUT.read_text(encoding="utf-8"))
    items = catalog["items"]
    targets = [it for it in items if it.get("type") in {"movies", "series"} and len(it.get("genres") or []) <= 1]
    before = len(targets)
    print(f"enrich: {before} movies/series have only a row name", file=sys.stderr)

    titled = 0
    for it in targets:
        extras = [g for g in genres_from_evidence(it["title"], title_only=True) if g != it["genres"][0]]
        if extras:
            it["genres"] = [it["genres"][0]] + extras
            titled += 1
    print(f"enrich: {titled} tagged from the title alone", file=sys.stderr)

    remaining = [it for it in items if it.get("type") in {"movies", "series"} and len(it.get("genres") or []) <= 1]
    print(f"enrich: fetching metadata for {len(remaining)} titles (1.2s spacing, cache reused)", file=sys.stderr)

    fetched = cached_hits = tagged = 0
    bot_blocked = False
    last_call = 0.0
    min_interval = 1.2

    for i, it in enumerate(remaining, 1):
        cached = cache_get("meta", it["id"])
        from_cache = bool(cached and cached.get("retried") and not cached.get("transient"))
        if from_cache:
            meta = cached
            cached_hits += 1
        else:
            wait = min_interval - (time.monotonic() - last_call)
            if wait > 0:
                time.sleep(wait)
            last_call = time.monotonic()
            meta = fetch_meta(it["id"])
            fetched += 1
            if fetched % 20 == 0:
                _save_catalog(catalog)
                print(f"enrich: fetched {fetched}, {i}/{len(remaining)} considered, saved progress", file=sys.stderr)
        if meta.get("bot"):
            bot_blocked = True
            print("enrich: YouTube bot check; stopping and saving progress", file=sys.stderr)
            break
        if meta.get("ok"):
            extras = [g for g in genres_from_evidence(
                meta.get("title") or it["title"],
                meta.get("description") or "",
                meta.get("tags") or [],
                meta.get("categories") or [],
            ) if g != it["genres"][0]]
            if extras:
                it["genres"] = [it["genres"][0]] + extras
                tagged += 1

    _save_catalog(catalog)
    after = sum(1 for it in items if it.get("type") in {"movies", "series"} and len(it.get("genres") or []) <= 1)
    print(json.dumps({
        "before_only_row": before,
        "tagged_from_title": titled,
        "fetched": fetched,
        "cache_hits": cached_hits,
        "tagged_from_metadata": tagged,
        "after_only_row": after,
        "bot_blocked": bot_blocked,
        "generated": catalog["generated"],
    }), file=sys.stderr)
    return 2 if bot_blocked else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-channel", type=int, default=8)
    ap.add_argument("--scan", type=int, default=90, help="uploads scanned per channel")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--refine", action="store_true",
                    help="verify the existing catalog, drop failures, and fill kids/cartoons")
    ap.add_argument("--target", type=int, default=48,
                    help="with --refine, aim for this many kids and this many cartoons (never pad)")
    ap.add_argument("--enrich-genres", action="store_true",
                    help="append real genres to movies/series that only have a row name")
    args = ap.parse_args()

    if args.refine:
        return refine(args)
    if args.enrich_genres:
        return enrich_genres(args)

    channels = load_channels()
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

    per_channel: dict[str, int] = {}
    items, sources, skipped = [], {}, []
    skip_trailers = trailer_ids()
    for (ch, e, section, row), v in zip(candidates, checks):
        if not v.get("ok"):
            skipped.append({"id": e["id"], "reason": v.get("reason")})
            continue
        if e["id"] in skip_trailers or per_channel.get(ch["name"], 0) >= args.per_channel:
            continue
        expected = channel_ids.get(ch["name"])
        if expected and v.get("channel_id") and v["channel_id"] != expected:
            skipped.append({"id": e["id"], "reason": "uploaded by a different channel"})
            continue
        per_channel[ch["name"]] = per_channel.get(ch["name"], 0) + 1
        banned = name_variants(ch["name"]) + [v.get("channel") or "", (v.get("uploader_id") or "").lstrip("@")]
        raw_title = v.get("title") or e.get("title") or ""
        items.append({
            "id": e["id"],
            "title": clean_title(raw_title, banned),
            "duration": int(v["duration"]),
            "type": section,
            "genres": genres_for(section, row, raw_title),
            "thumbnail": f"https://i.ytimg.com/vi/{e['id']}/hqdefault.jpg",
        })
        sources[e["id"]] = v.get("channel_id")
    write_catalog(items, sources, channels, channel_ids, skipped)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
