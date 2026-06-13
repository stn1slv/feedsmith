"""Extractor for Computers & Technology books via the Google Books API.

Built to surface recent English-language books matching a search term (e.g.
"MuleSoft", "Apache Kafka", "Model Context Protocol") under the Computers
subject. The Google Books volumes API is free and needs no auth, so it fits the
project's no-secrets / structured-data ethos. The per-feed search term comes from
``FeedConfig.query``; the category is fixed here, so adding another query is a
``feeds.yaml``-only change.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx

from feedsmith.config import FeedConfig
from feedsmith.exceptions import ConfigError, FetchError, ParseError
from feedsmith.extractors.base import clean_text
from feedsmith.logging import get_logger
from feedsmith.models import Post

logger = get_logger(__name__)

# The fixed category for this tool: Amazon's "Computers & Technology" maps to the
# Google Books "Computers" subject. Combined with the per-feed query term.
_SUBJECT = "subject:Computers"

# Google Books caps maxResults at 40; the service layer truncates to max_items.
_MAX_RESULTS = 40

# Optional API key. Without it the API works but shares a low anonymous quota
# (HTTP 429); a key raises the quota. Kept in the environment, never in feeds.yaml
# (which ships inside the wheel) and never logged.
_API_KEY_ENV = "GOOGLE_BOOKS_API_KEY"


def _clean(value: object) -> str | None:
    """Clean a text field, tolerating non-string JSON values by ignoring them."""
    return clean_text(value) if isinstance(value, str) else None


class GoogleBooksExtractor:
    """Fetch English Computers & Technology books matching ``cfg.query``.

    Reusable for any search term: only ``feeds.yaml`` needs a new entry.
    """

    def fetch(self, cfg: FeedConfig, client: httpx.Client) -> list[Post]:
        if not cfg.query:
            raise ConfigError(f"google_books feed '{cfg.id}' requires a 'query'")

        params: dict[str, str | int] = {
            "q": f"{cfg.query} {_SUBJECT}",
            "orderBy": "newest",
            "printType": "books",
            "langRestrict": "en",
            "country": "US",
            "maxResults": min(cfg.max_items, _MAX_RESULTS),
        }
        api_key = os.environ.get(_API_KEY_ENV)
        if api_key:
            params["key"] = api_key
        try:
            response = client.get(cfg.url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as err:
            raise FetchError(f"Failed to query Google Books API at {cfg.url}") from err

        try:
            payload = response.json()
        except ValueError as err:
            raise ParseError(f"Google Books API did not return JSON: {cfg.url}") from err

        if not isinstance(payload, dict):
            raise ParseError(f"Expected a JSON object from Google Books API: {cfg.url}")

        # A query with no matches omits "items" entirely; that is a valid empty feed.
        items = payload.get("items", [])
        if not isinstance(items, list):
            raise ParseError(f"Expected an 'items' array from Google Books API: {cfg.url}")

        posts = [post for item in items if isinstance(item, dict) if (post := self._to_post(item)) is not None]
        logger.info("google_books.fetched", feed=cfg.id, count=len(posts))
        return posts

    def _to_post(self, item: dict[str, Any]) -> Post | None:
        """Map one volume to a Post, or None to skip it.

        Volumes are skipped (not errors) when they are non-English or lack a
        usable publication date — both are expected in search results and have
        no place in a date-ordered, English-only feed.
        """
        vi = item.get("volumeInfo")
        if not isinstance(vi, dict):
            return None

        language = vi.get("language")
        if language and language != "en":
            return None

        published = self._parse_date(vi.get("publishedDate"))
        if published is None:
            return None

        volume_id = item.get("id")
        url = vi.get("canonicalVolumeLink") or vi.get("infoLink")
        title = self._title(vi)
        if not volume_id or not url or not title:
            return None

        authors = vi.get("authors")
        names = [a for a in authors if isinstance(a, str)] if isinstance(authors, list) else []
        categories = vi.get("categories")
        cats = [c for c in categories if isinstance(c, str)] if isinstance(categories, list) else []
        return Post(
            id=str(volume_id),
            title=title,
            url=url,
            published=published,
            summary=_clean(vi.get("description")),
            author=", ".join(names) or None,
            categories=cats,
        )

    @staticmethod
    def _title(vi: dict[str, Any]) -> str | None:
        title = _clean(vi.get("title"))
        subtitle = _clean(vi.get("subtitle"))
        if title and subtitle:
            return f"{title}: {subtitle}"
        return title

    @staticmethod
    def _parse_date(value: object) -> datetime | None:
        # publishedDate has variable precision and no timezone: "2024",
        # "2024-03", or "2024-03-15". Pad missing parts and stamp UTC.
        if not isinstance(value, str) or not value:
            return None
        parts = value.split("-")
        try:
            year = int(parts[0])
            month = int(parts[1]) if len(parts) > 1 else 1
            day = int(parts[2]) if len(parts) > 2 else 1
            return datetime(year, month, day, tzinfo=UTC)
        except (ValueError, IndexError):
            return None
