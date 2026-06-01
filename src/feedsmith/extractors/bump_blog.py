"""Extractor for the Bump.sh blog, a Bridgetown static site with no feed.

The listing page renders a "Recent posts" grid of cards. Each card carries a
title, link, excerpt, category, and date, but exposes no embedded JSON, so the
cards are read from the rendered HTML with BeautifulSoup.
"""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from feedsmith.config import FeedConfig
from feedsmith.exceptions import FetchError, ParseError
from feedsmith.extractors.base import clean_text
from feedsmith.logging import get_logger
from feedsmith.models import Post

logger = get_logger(__name__)


class BumpBlogExtractor:
    """Fetch posts from the Bump.sh blog's rendered "Recent posts" cards."""

    def fetch(self, cfg: FeedConfig, client: httpx.Client) -> list[Post]:
        try:
            response = client.get(cfg.url)
            response.raise_for_status()
        except httpx.HTTPError as err:
            raise FetchError(f"Failed to fetch Bump.sh blog page {cfg.url}") from err

        cards = self._extract_cards(response.text, cfg.url)
        posts = [self._to_post(card, cfg.site_url) for card in cards]
        logger.info("bump_blog.fetched", feed=cfg.id, count=len(posts))
        return posts

    def _extract_cards(self, html_text: str, url: str) -> list[Tag]:
        soup = BeautifulSoup(html_text, "html.parser")
        # Featured cards are the only blocks carrying an excerpt; archive rows below
        # share other classes but never an excerpt, so the card div is the discriminator.
        cards = [card for card in soup.find_all("div", class_="group/excerpt") if isinstance(card, Tag)]
        if not cards:
            raise ParseError(f"No blog post cards found on {url}")
        return cards

    def _to_post(self, card: Tag, site_url: str) -> Post:
        try:
            link = card.find("a", class_="stretched-link")
            if not isinstance(link, Tag):
                raise ParseError("card has no post link")
            href = link.get("href")
            if not isinstance(href, str):
                raise ParseError("card link has no href")

            date_el = card.find("p", class_="body-4")
            if not isinstance(date_el, Tag):
                raise ParseError("card has no date")

            excerpt_el = card.find("p", class_="body-3")
            summary = clean_text(excerpt_el.get_text()) if isinstance(excerpt_el, Tag) else None

            category_el = card.find("span", class_="body-4")
            category = clean_text(category_el.get_text()) if isinstance(category_el, Tag) else None

            return Post(
                id=href.strip("/").split("/")[-1],
                title=clean_text(link.get_text()) or "(untitled)",
                url=urljoin(site_url, href),
                published=self._parse_date(date_el.get_text(strip=True)),
                summary=summary,
                categories=[category] if category else [],
            )
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            raise ParseError("Malformed Bump.sh card") from err

    @staticmethod
    def _parse_date(value: str) -> datetime:
        # Dates are listed as MM/DD/YYYY with no time or offset; stamp UTC.
        return datetime.strptime(value, "%m/%d/%Y").replace(tzinfo=UTC)
