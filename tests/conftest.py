"""Shared pytest fixtures."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from feedsmith.config import FeedConfig
from feedsmith.models import FeedMeta, Post

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _configure_logging():
    """Bind structlog to the current (per-test) captured stderr."""
    from feedsmith.logging import configure_logging

    configure_logging()


@pytest.fixture
def boomi_json() -> str:
    return (FIXTURES / "boomi_posts.json").read_text(encoding="utf-8")


@pytest.fixture
def kong_html() -> str:
    return (FIXTURES / "kong_blog.html").read_text(encoding="utf-8")


@pytest.fixture
def boomi_config() -> FeedConfig:
    return FeedConfig(
        id="boomi",
        title="Boomi Blog",
        extractor="wordpress_api",
        url="https://boomi.com/wp-json/wp/v2/blog",
        site_url="https://boomi.com/blog/",
        max_items=20,
    )


@pytest.fixture
def kong_config() -> FeedConfig:
    return FeedConfig(
        id="kong",
        title="Kong Blog",
        extractor="nextjs_blog",
        url="https://konghq.com/blog/page/1",
        site_url="https://konghq.com/blog/",
        max_items=20,
    )


@pytest.fixture
def client() -> httpx.Client:
    return httpx.Client()


@pytest.fixture
def sample_posts() -> list[Post]:
    return [
        Post(
            id="2",
            title="Second & newest post",
            url="https://example.com/blog/second",
            published=datetime(2026, 2, 1, 9, 0, tzinfo=UTC),
            summary="Summary two.",
            author="Ada Lovelace",
            categories=["news"],
        ),
        Post(
            id="1",
            title="First post",
            url="https://example.com/blog/first",
            published=datetime(2026, 1, 1, 8, 0, tzinfo=UTC),
            summary=None,
        ),
    ]


@pytest.fixture
def sample_meta() -> FeedMeta:
    return FeedMeta(id="example", title="Example Blog", site_url="https://example.com/blog/")
