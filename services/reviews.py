"""Visitor feedback / live reviews storage."""

from __future__ import annotations

import html
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data" / "reviews.json"
_LOCK = threading.Lock()
_RATE: dict[str, float] = {}

NAME_RE = re.compile(r"^[\w\s.'-]{2,40}$", re.UNICODE)
MAX_REVIEWS = 500
RATE_SECONDS = 45


def _path() -> Path:
    override = os.getenv("REVIEWS_PATH", "").strip()
    return Path(override) if override else DEFAULT_PATH


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load() -> list[dict[str, Any]]:
    path = _path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save(rows: list[dict[str, Any]]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def list_reviews(limit: int = 50) -> list[dict[str, Any]]:
    with _LOCK:
        rows = _load()
    rows = sorted(rows, key=lambda r: r.get("created_at") or "", reverse=True)
    return rows[: max(1, min(limit, 100))]


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
    # prune old entries
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
    if honeypot.strip():
        return None, "Could not submit review."
    if not _allowed_ip(ip or "unknown"):
        return None, "Please wait a moment before posting again."

    name = html.escape((name or "").strip())
    message = html.escape((message or "").strip())
    # unescape for storage of plain text then re-escape on display is safer as plain
    name = html.unescape(name)
    message = html.unescape(message)

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

    with _LOCK:
        rows = _load()
        rows.append(review)
        rows = sorted(rows, key=lambda r: r.get("created_at") or "", reverse=True)[:MAX_REVIEWS]
        _save(rows)
    return review, None
