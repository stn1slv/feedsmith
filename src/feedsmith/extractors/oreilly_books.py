"""Extractor for recent O'Reilly Media books via the O'Reilly search API.

O'Reilly's content-search endpoint is public (no account or key) and returns
structured JSON. Filtered to ``formats=book`` and the O'Reilly Media publisher,
ordered by catalog-add date, it yields the newest O'Reilly titles. This is the
direct, structured-data source the project prefers, so O'Reilly books no longer
need to be sourced through Google Books.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import httpx

from feedsmith.config import FeedConfig
from feedsmith.exceptions import FetchError, ParseError
from feedsmith.extractors.base import clean_text
from feedsmith.logging import get_logger
from feedsmith.models import Post

logger = get_logger(__name__)

# Fixed publisher filter for this dedicated source.
_PUBLISHER = "O'Reilly Media, Inc."

# Human-facing base for a book's relative ``web_url``.
_WEB_BASE = "https://www.oreilly.com"

# The O'Reilly API returns up to 200 results per request (larger values error).
_MAX_LIMIT = 200

# Fetch a few extra beyond max_items so the occasional skipped result (non-en,
# non-book, undated, not-yet-released) does not starve the feed; the service layer truncates.
_LIMIT_BUFFER = 10


def _now() -> datetime:
    """Current UTC time. A seam so the release-date cutoff can be frozen in tests."""
    return datetime.now(UTC)


def _max_issued(now: datetime) -> datetime:
    """First instant of the next calendar month. Books issued before this are kept.

    Drops not-yet-released titles whose publication date is next month or later.
    """
    month, year = now.month + 1, now.year
    if month > 12:
        month, year = 1, year + 1
    return datetime(year, month, 1, tzinfo=UTC)


def _clean(value: object) -> str | None:
    """Clean a text field, tolerating non-string JSON values by ignoring them."""
    return clean_text(value) if isinstance(value, str) else None


class OreillyBooksExtractor:
    """Fetch the newest O'Reilly Media books from the O'Reilly search API."""

    def fetch(self, cfg: FeedConfig, client: httpx.Client) -> list[Post]:
        params: dict[str, str | int] = {
            "query": "*",
            "formats": "book",
            "publishers": _PUBLISHER,
            "sort": "date_added",
            "order": "desc",
            "limit": min(cfg.max_items + _LIMIT_BUFFER, _MAX_LIMIT),
        }
        try:
            response = client.get(cfg.url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as err:
            raise FetchError(f"Failed to query O'Reilly search API at {cfg.url}") from err

        try:
            payload = response.json()
        except ValueError as err:
            raise ParseError(f"O'Reilly search API did not return JSON: {cfg.url}") from err

        if not isinstance(payload, dict):
            raise ParseError(f"Expected a JSON object from O'Reilly search API: {cfg.url}")

        # A query with no matches still returns a "results" array; an empty one is a valid empty feed.
        results = payload.get("results", [])
        if not isinstance(results, list):
            raise ParseError(f"Expected a 'results' array from O'Reilly search API: {cfg.url}")

        cutoff = _max_issued(_now())
        posts = [
            post for item in results if isinstance(item, dict) if (post := self._to_post(item, cutoff)) is not None
        ]
        logger.info("oreilly_books.fetched", feed=cfg.id, count=len(posts))
        return posts

    def _to_post(self, item: dict[str, Any], cutoff: datetime) -> Post | None:
        """Map one search result to a Post, or None to skip it.

        Results are skipped (not errors) when they are not books, are non-English,
        lack a usable id, title, link, publication date, or catalog-add date, or are
        not yet released (publication date ``issued`` at or after ``cutoff``) — all
        expected in a broad search response and out of place in this feed.

        ``Post.published`` is the real publication date (``issued``); ``Post.updated``
        is the catalog-add date (``date_added``).
        """
        fmt = item.get("format")
        if fmt is not None and fmt != "book":
            return None

        language = item.get("language")
        if language and language != "en":
            return None

        published = self._parse_datetime(item.get("issued"))
        if published is None or published >= cutoff:
            return None

        updated = self._parse_datetime(item.get("date_added"))
        web_url = item.get("web_url")
        title = _clean(item.get("title"))
        book_id = item.get("ourn") or item.get("archive_id") or item.get("isbn")
        if updated is None or not isinstance(web_url, str) or not web_url or not title or not book_id:
            return None

        authors = item.get("authors")
        names = [a for a in authors if isinstance(a, str)] if isinstance(authors, list) else []
        return Post(
            id=str(book_id),
            title=title,
            url=urljoin(_WEB_BASE, web_url),
            published=published,
            updated=updated,
            summary=_clean(item.get("description")),
            author=", ".join(names) or None,
        )

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        # date_added is ISO 8601 with a trailing "Z" and fractional seconds
        # (e.g. "2026-06-16T21:35:21.108Z"); fromisoformat handles both on 3.13.
        # A value without an offset is stamped UTC to satisfy the Post validator.
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
