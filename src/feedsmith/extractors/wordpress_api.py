"""Extractor for blogs exposing the WordPress REST API (``wp-json/wp/v2/posts``)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from feedsmith.config import FeedConfig
from feedsmith.exceptions import FetchError, ParseError
from feedsmith.extractors.base import clean_text
from feedsmith.logging import get_logger
from feedsmith.models import Post

logger = get_logger(__name__)

# Only the fields we actually map, to keep responses small.
_FIELDS = "id,link,date_gmt,title,excerpt"


class WordPressApiExtractor:
    """Fetch posts from a WordPress site's REST API.

    Reusable for any WordPress blog: only ``feeds.yaml`` needs a new entry.
    """

    def fetch(self, cfg: FeedConfig, client: httpx.Client) -> list[Post]:
        params: dict[str, str | int] = {"per_page": cfg.max_items, "_fields": _FIELDS}
        try:
            response = client.get(cfg.url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as err:
            raise FetchError(f"Failed to fetch WordPress posts from {cfg.url}") from err

        try:
            items = response.json()
        except ValueError as err:
            raise ParseError(f"WordPress API did not return JSON: {cfg.url}") from err

        if not isinstance(items, list):
            raise ParseError(f"Expected a JSON array of posts from {cfg.url}")

        posts = [self._to_post(item) for item in items if isinstance(item, dict)]
        logger.info("wordpress_api.fetched", feed=cfg.id, count=len(posts))
        return posts

    def _to_post(self, item: dict[str, Any]) -> Post:
        try:
            published = self._parse_date(item["date_gmt"])
            return Post(
                id=str(item["id"]),
                title=clean_text(item.get("title", {}).get("rendered")) or "(untitled)",
                url=item["link"],
                published=published,
                summary=clean_text(item.get("excerpt", {}).get("rendered")),
            )
        except (KeyError, TypeError, ValueError) as err:
            raise ParseError(f"Malformed WordPress post: {item.get('id', '?')}") from err

    @staticmethod
    def _parse_date(value: str) -> datetime:
        # date_gmt is UTC but carries no offset (e.g. "2025-12-04T13:40:46").
        return datetime.fromisoformat(value).replace(tzinfo=UTC)
