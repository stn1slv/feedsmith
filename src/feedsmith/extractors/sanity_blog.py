"""Extractor for blogs backed by a public Sanity CMS (GROQ query API).

Built for the Treblle blog: a Next.js App Router site with no ``__NEXT_DATA__``
blob, whose content lives in a public Sanity dataset queryable over the GROQ API
with no auth. The projection below assumes a ``blogPost`` document schema.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import httpx

from feedsmith.config import FeedConfig
from feedsmith.exceptions import FetchError, ParseError
from feedsmith.extractors.base import clean_text
from feedsmith.logging import get_logger
from feedsmith.models import Post

logger = get_logger(__name__)

# GROQ projection tuned to a ``blogPost`` schema. No ``order()``/slice here: the
# service layer sorts (published desc) and truncates to ``max_items``.
_GROQ = (
    '*[_type=="blogPost" && defined(slug.current)]{'
    '"id": slug.current, title, "slug": slug.current, excerpt, '
    '"published": coalesce(publishedAt, _createdAt), "author": author->name}'
)


class SanityBlogExtractor:
    """Fetch posts from a Sanity-backed blog via its public GROQ query API."""

    def fetch(self, cfg: FeedConfig, client: httpx.Client) -> list[Post]:
        try:
            response = client.get(cfg.url, params={"query": _GROQ})
            response.raise_for_status()
        except httpx.HTTPError as err:
            raise FetchError(f"Failed to query Sanity API at {cfg.url}") from err

        try:
            payload = response.json()
        except ValueError as err:
            raise ParseError(f"Sanity API did not return JSON: {cfg.url}") from err

        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, list):
            raise ParseError(f"Expected a 'result' array from Sanity API: {cfg.url}")

        posts = [self._to_post(item, cfg.site_url) for item in result if isinstance(item, dict)]
        logger.info("sanity_blog.fetched", feed=cfg.id, count=len(posts))
        return posts

    def _to_post(self, item: dict[str, Any], site_url: str) -> Post:
        try:
            slug = item["slug"]
            return Post(
                id=slug,
                title=clean_text(item.get("title")) or "(untitled)",
                url=urljoin(site_url, slug),
                published=self._parse_date(item["published"]),
                summary=clean_text(item.get("excerpt")),
                author=clean_text(item.get("author")),
            )
        except (KeyError, TypeError, ValueError) as err:
            raise ParseError(f"Malformed Sanity post: {item.get('slug', '?')}") from err

    @staticmethod
    def _parse_date(value: str) -> datetime:
        # Sanity timestamps are ISO 8601 with a trailing "Z" (e.g.
        # "2026-05-28T13:01:00.000Z"); fromisoformat parses it tz-aware.
        return datetime.fromisoformat(value)
