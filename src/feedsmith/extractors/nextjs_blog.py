"""Extractor for Next.js blogs that embed posts in a ``__NEXT_DATA__`` script.

Built for the Kong blog, whose listing page carries structured post data under
``props.pageProps.cardsPaged.cards``.
"""

from __future__ import annotations

import json
import re
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

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
    re.DOTALL,
)


class NextjsBlogExtractor:
    """Fetch posts from a Next.js blog's embedded ``__NEXT_DATA__`` JSON."""

    def fetch(self, cfg: FeedConfig, client: httpx.Client) -> list[Post]:
        try:
            response = client.get(cfg.url)
            response.raise_for_status()
        except httpx.HTTPError as err:
            raise FetchError(f"Failed to fetch Next.js blog page {cfg.url}") from err

        cards = self._extract_cards(response.text, cfg.url)
        posts = [self._to_post(card, cfg.site_url) for card in cards if isinstance(card, dict)]
        logger.info("nextjs_blog.fetched", feed=cfg.id, count=len(posts))
        return posts

    def _extract_cards(self, html_text: str, url: str) -> list[Any]:
        match = _NEXT_DATA_RE.search(html_text)
        if match is None:
            raise ParseError(f"No __NEXT_DATA__ script found on {url}")
        try:
            data = json.loads(match.group(1))
            cards = data["props"]["pageProps"]["cardsPaged"]["cards"]
        except (ValueError, KeyError, TypeError) as err:
            raise ParseError(f"Unexpected __NEXT_DATA__ structure on {url}") from err
        if not isinstance(cards, list):
            raise ParseError(f"Expected a list of cards on {url}")
        return cards

    def _to_post(self, card: dict[str, Any], site_url: str) -> Post:
        try:
            href = card["link"]["href"]
            authors = card.get("authors") or []
            author = authors[0].get("title") if authors and isinstance(authors[0], dict) else None
            term = card.get("term") or {}
            categories = [term["title"]] if isinstance(term, dict) and term.get("title") else []
            return Post(
                id=str(card["id"]),
                title=clean_text(card.get("title")) or "(untitled)",
                url=urljoin(site_url, href),
                published=self._parse_date(card["publishedAt"]),
                summary=clean_text(card.get("excerpt")),
                author=clean_text(author),
                categories=categories,
            )
        except (KeyError, TypeError, ValueError) as err:
            raise ParseError(f"Malformed Next.js card: {card.get('id', '?')}") from err

    @staticmethod
    def _parse_date(value: str) -> datetime:
        # publishedAt is ISO 8601 with a trailing "Z" (e.g. "2026-05-26T14:36:03.202Z").
        return datetime.fromisoformat(value)
