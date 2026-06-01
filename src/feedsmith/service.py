"""Service layer: orchestrates config, extractors, and feed building.

This module contains the core logic and is independent of the CLI. It raises
``FeedsmithError`` subclasses; the CLI boundary translates them to exit codes.
"""

from __future__ import annotations

import httpx

from feedsmith.config import AppConfig, FeedConfig
from feedsmith.extractors.registry import get_extractor
from feedsmith.feed import build_atom
from feedsmith.logging import get_logger
from feedsmith.models import FeedMeta, Post

logger = get_logger(__name__)


def _feed_meta(cfg: FeedConfig) -> FeedMeta:
    return FeedMeta(id=cfg.id, title=cfg.title, site_url=cfg.site_url)


def generate_feed(cfg: FeedConfig, client: httpx.Client) -> str:
    """Produce the Atom feed XML for a single configured blog.

    Posts are sorted newest-first and truncated to ``cfg.max_items``.
    """
    extractor = get_extractor(cfg.extractor)
    posts = extractor.fetch(cfg, client)
    posts = _ordered(posts)[: cfg.max_items]
    logger.info("feed.generated", feed=cfg.id, entries=len(posts))
    return build_atom(_feed_meta(cfg), posts)


def generate_all(config: AppConfig, client: httpx.Client) -> dict[str, str]:
    """Generate feeds for every configured blog.

    Returns a mapping of feed id to Atom XML. Raises on the first failure.
    """
    return {feed_id: generate_feed(config.feeds[feed_id], client) for feed_id in config.ids()}


def _ordered(posts: list[Post]) -> list[Post]:
    return sorted(posts, key=lambda p: p.published, reverse=True)
