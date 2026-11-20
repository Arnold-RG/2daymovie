"""Rank verified 2DayMovie titles using YouTube popularity statistics.

This module does not scrape or download videos. Rankings are computed from
official API metadata, and only verified, embeddable titles can be shown.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

COLLECTIONS = ("movies", "series", "ai_animation", "kids_movies", "kids_series")
VIDEO_ID_FIELDS = ("video_id", "title", "collection", "views", "published_at", "embed_allowed", "full_length_verified", "rights_reviewed")


def eligible(item: dict[str, Any]) -> bool:
    return (
        item.get("collection") in COLLECTIONS
        and bool(item.get("embed_allowed"))
        and bool(item.get("full_length_verified"))
        and bool(item.get("rights_reviewed"))
        and isinstance(item.get("views"), int)
        and not isinstance(item.get("views"), bool)
        and item["views"] >= 0
        and isinstance(item.get("video_id"), str)
        and len(item["video_id"]) == 11
    )


def most_viewed(items: list[dict[str, Any]], collection: str, limit: int = 20) -> list[dict[str, Any]]:
    """Rank within a category, never mixing kids' titles with adult cinema."""
    if collection not in COLLECTIONS:
        raise ValueError("Unknown collection")
    if not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100")
    selected = [item for item in items if eligible(item) and item["collection"] == collection]
    return sorted(selected, key=lambda item: (-item["views"], item["video_id"]))[:limit]


def most_viewed_by_country(items: list[dict[str, Any]], collection: str, country: str, limit: int = 20) -> list[dict[str, Any]]:
    if not country.strip():
        raise ValueError("Country is required")
    return [item for item in most_viewed(items, collection, 100) if item.get("country", "").casefold() == country.casefold()][:limit]


def refresh_video_metadata(video: dict[str, Any]) -> dict[str, Any]:
    """Normalize a YouTube videos.list result; don't treat metadata as rights approval."""
    details = video.get("contentDetails") or {}
    status = video.get("status") or {}
    stats = video.get("statistics") or {}
    return {
        "video_id": video.get("id"),
        "title": (video.get("snippet") or {}).get("title", ""),
        "views": int(stats.get("viewCount", 0)),
        "duration_iso8601": details.get("duration"),
        "captions_declared": details.get("caption") == "true",
        "embed_allowed": status.get("embeddable") is True,
        "metadata_checked_at": datetime.now(timezone.utc).isoformat(),
        "full_length_verified": False,
        "rights_reviewed": False,
    }
