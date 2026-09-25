"""Visitor feedback / live reviews storage.

Persists to Postgres in production (set DATABASE_URL). Falls back to a local
SQLite file for local development only.

Why this replaced the old JSON-file version:
1. Render's free web service plan has NO persistent disk. Every redeploy
   (every git push) rebuilds the container from scratch, so a local
   data/reviews.json file resets to whatever was last committed — any
   reviews submitted since the last deploy are gone.
2. render.yaml runs gunicorn with 2 worker PROCESSES. The old code used
   threading.Lock(), which only protects against concurrent threads in the
   SAME process — it does nothing across separate worker processes. Two
   visitors submitting at the same moment, routed to different workers,
   could each read-modify-write the file and one submission would silently
   overwrite the other.

Using a real database (Postgres) fixes both: the data lives outside the
container entirely, and the database itself handles concurrent writes
safely.
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

NAME_RE = re.compile(r"^[\w\s.'-]{2,40}$", re.UNICODE)
MAX_REVIEWS = 500
RATE_SECONDS = 45
_RATE: dict[str, float] = {}
_INITIALIZED = False


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def _is_postgres() -> bool:
    url = _database_url()
    return url.startswith(("postgres://", "postgresql://"))


def _sqlite_path() -> Path:
    override = os.getenv("REVIEWS_SQLITE_PATH", "").strip()
    if override:
        return Path(override)
    # Back-compat: older tests/docs used REVIEWS_PATH for a JSON file.
    legacy = os.getenv("REVIEWS_PATH", "").strip()
    if legacy and legacy.lower().endswith(".db"):
        return Path(legacy)
    if legacy:
        # Point SQLite next to the old JSON path during migration/tests.
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


def _ensure_db() -> None:
    if not _INITIALIZED:
        _init_db()


def _import_legacy_json_once() -> None:
    """Best-effort restore from a leftover data/reviews.json (or REVIEWS_PATH)."""
    candidates: list[Path] = []
    legacy_env = os.getenv("REVIEWS_PATH", "").strip()
    if legacy_env and legacy_env.lower().endswith(".json"):
        candidates.append(Path(legacy_env))
    candidates.append(LEGACY_JSON)

    rows: list[dict[str, Any]] = []
    source: Path | None = None
    for path in candidates:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, list) and data:
            rows = [r for r in data if isinstance(r, dict)]
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
                # Duplicate primary key / already migrated.
                continue
        conn.commit()

    if imported:
        # Keep the JSON as a backup, but stop re-importing by renaming.
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
    p = _placeholder()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, name, rating, message, created_at FROM reviews "
            f"ORDER BY created_at DESC LIMIT {p}",
            (limit,),
        )
        rows = cur.fetchall()
    return [
        {"id": r[0], "name": r[1], "rating": r[2], "message": r[3], "created_at": r[4]}
        for r in rows
    ]


def stats() -> dict[str, Any]:
    rows = list_reviews(limit=MAX_REVIEWS)
    if not rows:
        return {"count": 0, "average": 0.0}
    ratings = [int(r.get("rating") or 0) for r in rows if r.get("rating")]
    avg = round(sum(ratings) / len(ratings), 1) if ratings else 0.0
    return {"count": len(rows), "average": avg}


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

        # Prune beyond MAX_REVIEWS, oldest first.
        cur.execute("SELECT id FROM reviews ORDER BY created_at DESC")
        all_ids = [r[0] for r in cur.fetchall()]
        if len(all_ids) > MAX_REVIEWS:
            stale = all_ids[MAX_REVIEWS:]
            qmarks = ",".join([p] * len(stale))
            cur.execute(f"DELETE FROM reviews WHERE id IN ({qmarks})", stale)
            conn.commit()

    return review, None
