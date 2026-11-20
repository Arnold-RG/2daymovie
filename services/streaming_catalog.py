"""Curated full-length YouTube sources for the replacement 2DayMovie platform.

Only add entries after checking that the uploader authorizes embedding and that
the video is a complete film or episode. No legacy trailer records are imported.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import re

VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
Kind = Literal["movie", "episode", "ai_movie", "ai_episode"]


@dataclass(frozen=True)
class Stream:
    video_id: str
    title: str
    kind: Kind
    creator: str
    series: str | None = None
    season: int | None = None
    episode: int | None = None
    verified_full_length: bool = False
    embed_allowed: bool = False
    rights_reviewed: bool = False

    def __post_init__(self) -> None:
        if not VIDEO_ID.fullmatch(self.video_id):
            raise ValueError("Invalid YouTube video ID")
        if not self.title.strip() or not self.creator.strip():
            raise ValueError("Title and creator are required")
        if self.kind in ("episode", "ai_episode"):
            if not self.series or not self.season or not self.episode:
                raise ValueError("Series episodes require series, season and episode")

    @property
    def publishable(self) -> bool:
        return self.verified_full_length and self.embed_allowed and self.rights_reviewed

    @property
    def embed_url(self) -> str:
        return f"https://www.youtube-nocookie.com/embed/{self.video_id}?playsinline=1"


# User-provided example. Not published until independently verified.
CANDIDATES = [
    Stream(
        video_id="dYq7Hw8jIHs",
        title="User-submitted full movie candidate",
        kind="movie",
        creator="Uploader verification pending",
    )
]


def published_streams() -> list[Stream]:
    """Return only full-length, embeddable, rights-reviewed content."""
    return [item for item in CANDIDATES if item.publishable]
