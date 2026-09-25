"""Visitor feedback / live reviews storage.

Primary store: Postgres when an official database link is available
(DATABASE_URL env, or data/official_database.url). Local SQLite is only
used as a last-resort fallback for offline development.

Also writes data/site_vault.json as a local mirror of reviews so you always
have a proper file snapshot of visitor data on disk (useful for backups /
migrations). On Render free tier that local file is still ephemeral — the
official durable store is the Postgres link in official_database.url.
"""

from __future__ import annotations

import html
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEGACY_JSON = ROOT / "data" / "reviews.json"
OFFICIAL_DB_LINK = ROOT / "data" / "official_database.url"
SITE_VAULT = ROOT / "data" / "site_vault.json"

NAME_RE = re.compile(r"^[\w\s.'-]{2,40}$", re.UNICODE)
MAX_REVIEWS = 500
RATE_SECONDS = 45
_RATE: dict[str, float] = {}
_INITIALIZED = False


def _read_official_database_url() -> str:
    """Official durable DB link: env first, then the project link file."""
    env = os.getenv("DATABASE_URL", "").strip()
    if env:
        return env

    candidates: list[Path] = []
    override = os.getenv("OFFICIAL_DATABASE_URL_FILE", "").strip()
    if override:
        candidates.append(Path(override))
    candidates.append(OFFICIAL_DB_LINK)

    for path in candidates:
        try:
            if path.is_file():
                raw = path.read_text(encoding="utf-8").strip()
                # Allow comments / blank lines in the official link file.
                for line in raw.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    return line
        except Exception:
            continue
    return ""


def _database_url() -> str:
    return _read_official_database_url()


def _is_postgres() -> bool:
    url = _database_url()
    return url.startswith(("postgres://", "postgresql://"))


def storage_backend() -> str:
    """Human-readable active store (for ops / health)."""
    if _is_postgres():
        return "postgres"
    return "sqlite"


def _sqlite_path() -> Path:
    override = os.getenv("REVIEWS_SQLITE_PATH", "").strip()
    if override:
        return Path(override)
    legacy = os.getenv("REVIEWS_PATH", "").strip()
    if legacy and legacy.lower().endswith(".db"):
        return Path(legacy)
    if legacy:
        return Path(legacy).with_suffix(".db")
    return ROOT / "data" / "reviews.db"


def _placeholder() -> str:
    return "%s" if _is_postgres() else "?"


def _connect():
    if _is_postgres():
        import psycopg2

        return psycopg2.connect(_database_url())

    import sqlite3

    path = _sqlite_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_db() -> None:
    global _INITIALIZED
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                rating INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    _INITIALIZED = True
    _import_legacy_json_once()
    _mirror_vault()


def _ensure_db() -> None:
    if not _INITIALIZED:
        _init_db()


def _all_reviews_raw() -> list[dict[str, Any]]:
    p = _placeholder()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, name, rating, message, created_at FROM reviews "
            f"ORDER BY created_at DESC LIMIT {p}",
            (MAX_REVIEWS,),
        )
        rows = cur.fetchall()
    return [
        {"id": r[0], "name": r[1], "rating": r[2], "message": r[3], "created_at": r[4]}
        for r in rows
    ]


def _mirror_vault() -> None:
    """Keep a proper on-disk JSON vault mirroring the official DB contents."""
    try:
        rows = _all_reviews_raw()
        payload = {
            "version": 1,
            "updated_at": _now_iso(),
            "backend": storage_backend(),
            "official_database_link_file": str(OFFICIAL_DB_LINK.name),
            "count": len(rows),
            "reviews": rows,
        }
        SITE_VAULT.parent.mkdir(parents=True, exist_ok=True)
        tmp = SITE_VAULT.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(SITE_VAULT)
    except Exception:
        # Vault is a mirror only — never fail a user-facing write because of it.
        pass


def _import_legacy_json_once() -> None:
    """Best-effort restore from leftover JSON / vault files."""
    candidates: list[Path] = []
    legacy_env = os.getenv("REVIEWS_PATH", "").strip()
    if legacy_env and legacy_env.lower().endswith(".json"):
        candidates.append(Path(legacy_env))
    candidates.extend([LEGACY_JSON, SITE_VAULT])

    rows: list[dict[str, Any]] = []
    source: Path | None = None
    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and isinstance(data.get("reviews"), list):
            parsed = [r for r in data["reviews"] if isinstance(r, dict)]
        elif isinstance(data, list):
            parsed = [r for r in data if isinstance(r, dict)]
        else:
            continue
        if parsed:
            rows = parsed
            source = path
            break
    if not rows or source is None:
        return

    p = _placeholder()
    imported = 0
    with _connect() as conn:
        cur = conn.cursor()
        for row in rows:
            rid = str(row.get("id") or uuid.uuid4())
            name = str(row.get("name") or "").strip()
            message = str(row.get("message") or "").strip()
            try:
                rating = int(row.get("rating") or 0)
            except (TypeError, ValueError):
                continue
            created = str(row.get("created_at") or _now_iso())
            if not name or not message or rating < 1 or rating > 5:
                continue
            try:
                cur.execute(
                    f"INSERT INTO reviews (id, name, rating, message, created_at) "
                    f"VALUES ({p}, {p}, {p}, {p}, {p})",
                    (rid, name, rating, message, created),
                )
                imported += 1
            except Exception:
                continue
        conn.commit()

    if imported and source in {LEGACY_JSON}:
        bak = source.with_suffix(source.suffix + ".migrated")
        try:
            if not bak.exists():
                source.replace(bak)
        except Exception:
            pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def list_reviews(limit: int = 50) -> list[dict[str, Any]]:
    _ensure_db()
    limit = max(1, min(limit, 100))
    return _all_reviews_raw()[:limit]


def stats() -> dict[str, Any]:
    rows = list_reviews(limit=MAX_REVIEWS)
    if not rows:
        return {"count": 0, "average": 0.0, "backend": storage_backend()}
    ratings = [int(r.get("rating") or 0) for r in rows if r.get("rating")]
    avg = round(sum(ratings) / len(ratings), 1) if ratings else 0.0
    return {"count": len(rows), "average": avg, "backend": storage_backend()}


def _allowed_ip(ip: str) -> bool:
    now = time.time()
    last = _RATE.get(ip, 0)
    if now - last < RATE_SECONDS:
        return False
    _RATE[ip] = now
    if len(_RATE) > 2000:
        cutoff = now - 3600
        for key in list(_RATE):
            if _RATE[key] < cutoff:
                del _RATE[key]
    return True


def add_review(
    *,
    name: str,
    rating: int,
    message: str,
    ip: str = "",
    honeypot: str = "",
) -> tuple[dict[str, Any] | None, str | None]:
    """Returns (review, error)."""
    _ensure_db()
    if honeypot.strip():
        return None, "Could not submit review."
    if not _allowed_ip(ip or "unknown"):
        return None, "Please wait a moment before posting again."

    name = html.unescape(html.escape((name or "").strip()))
    message = html.unescape(html.escape((message or "").strip()))
    name = re.sub(r"\s+", " ", name).strip()
    message = re.sub(r"\s+", " ", message).strip()

    if not NAME_RE.match(name):
        return None, "Name must be 2–40 letters (spaces and . ' - allowed)."
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        return None, "Choose a rating from 1 to 5."
    if rating < 1 or rating > 5:
        return None, "Choose a rating from 1 to 5."
    if len(message) < 8 or len(message) > 500:
        return None, "Review must be between 8 and 500 characters."

    review = {
        "id": str(uuid.uuid4()),
        "name": name,
        "rating": rating,
        "message": message,
        "created_at": _now_iso(),
    }

    p = _placeholder()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO reviews (id, name, rating, message, created_at) "
            f"VALUES ({p}, {p}, {p}, {p}, {p})",
            (
                review["id"],
                review["name"],
                review["rating"],
                review["message"],
                review["created_at"],
            ),
        )
        conn.commit()

        cur.execute("SELECT id FROM reviews ORDER BY created_at DESC")
        all_ids = [r[0] for r in cur.fetchall()]
        if len(all_ids) > MAX_REVIEWS:
            stale = all_ids[MAX_REVIEWS:]
            qmarks = ",".join([p] * len(stale))
            cur.execute(f"DELETE FROM reviews WHERE id IN ({qmarks})", stale)
            conn.commit()

    _mirror_vault()
    return review, None
