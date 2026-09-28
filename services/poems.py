"""Love poems catalog helpers for the Amora collection."""

from __future__ import annotations

from data import love_poems


def all_poems() -> list[dict]:
    return love_poems.all_poems()


def get_poem(slug: str) -> dict | None:
    return love_poems.get_poem(slug)


def featured_poem() -> dict:
    return love_poems.featured_poem()


def moods() -> list[str]:
    return love_poems.moods()


def neighboring(slug: str) -> tuple[dict | None, dict | None]:
    poems = all_poems()
    for index, poem in enumerate(poems):
        if poem["slug"] == slug:
            prev_poem = poems[index - 1] if index > 0 else None
            next_poem = poems[index + 1] if index + 1 < len(poems) else None
            return prev_poem, next_poem
    return None, None
