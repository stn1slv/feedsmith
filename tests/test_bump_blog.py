"""Tests for the Bump.sh HTML-scraping extractor."""

from __future__ import annotations

from datetime import UTC

import httpx
import pytest
import respx

from feedsmith.exceptions import FetchError, ParseError
from feedsmith.extractors.bump_blog import BumpBlogExtractor


@respx.mock
def test_fetch_maps_cards(bump_config, bump_html, client):
    respx.get(bump_config.url).mock(return_value=httpx.Response(200, text=bump_html))
    posts = BumpBlogExtractor().fetch(bump_config, client)

    assert len(posts) == 2
    first = posts[0]
    assert first.id == "arazzo-complete-guide"
    assert first.title == "Arazzo: The complete guide"
    assert first.url == "https://bump.sh/blog/arazzo-complete-guide/"
    assert first.summary is not None
    assert first.summary.startswith("After releasing the Arazzo Cheat Sheet")
    assert first.categories == ["Tech"]
    assert first.published.year == 2026
    assert first.published.tzinfo == UTC
    assert first.author is None


@respx.mock
def test_unescapes_entities_in_title(bump_config, bump_html, client):
    respx.get(bump_config.url).mock(return_value=httpx.Response(200, text=bump_html))
    posts = BumpBlogExtractor().fetch(bump_config, client)
    assert posts[1].title == "OpenAPI & AsyncAPI compared"


@respx.mock
def test_archive_rows_excluded(bump_config, bump_html, client):
    respx.get(bump_config.url).mock(return_value=httpx.Response(200, text=bump_html))
    posts = BumpBlogExtractor().fetch(bump_config, client)
    slugs = {post.id for post in posts}
    assert "5-improvements-to-openapi-operation-documentation" not in slugs


@respx.mock
def test_http_error_raises_fetch_error(bump_config, client):
    respx.get(bump_config.url).mock(return_value=httpx.Response(503))
    with pytest.raises(FetchError):
        BumpBlogExtractor().fetch(bump_config, client)


@respx.mock
def test_no_cards_raises_parse_error(bump_config, client):
    respx.get(bump_config.url).mock(return_value=httpx.Response(200, text="<html>no cards</html>"))
    with pytest.raises(ParseError, match="No blog post cards"):
        BumpBlogExtractor().fetch(bump_config, client)
