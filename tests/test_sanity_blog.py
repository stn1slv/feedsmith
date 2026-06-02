"""Tests for the Sanity GROQ API extractor."""

from __future__ import annotations

from datetime import UTC

import httpx
import pytest
import respx

from feedsmith.exceptions import FetchError, ParseError
from feedsmith.extractors.sanity_blog import SanityBlogExtractor


@respx.mock
def test_fetch_maps_posts(treblle_config, treblle_json, client):
    respx.get(treblle_config.url).mock(return_value=httpx.Response(200, text=treblle_json))
    posts = SanityBlogExtractor().fetch(treblle_config, client)

    assert len(posts) == 3
    # Posts come back in dataset order; the service layer sorts by published desc.
    first = posts[0]
    assert first.id == "headless-ui-bridging-observability-gap"
    assert first.title == "Headless UI: Bridging the Observability Gap"
    assert first.url == "https://treblle.com/blog/headless-ui-bridging-observability-gap"
    assert first.summary is not None
    assert first.summary.startswith("Headless architecture is changing")
    assert first.published.year == 2026
    assert first.published.tzinfo == UTC
    assert first.author is None


@respx.mock
def test_http_error_raises_fetch_error(treblle_config, client):
    respx.get(treblle_config.url).mock(return_value=httpx.Response(503))
    with pytest.raises(FetchError):
        SanityBlogExtractor().fetch(treblle_config, client)


@respx.mock
def test_non_json_raises_parse_error(treblle_config, client):
    respx.get(treblle_config.url).mock(return_value=httpx.Response(200, text="<html>nope"))
    with pytest.raises(ParseError):
        SanityBlogExtractor().fetch(treblle_config, client)


@respx.mock
def test_missing_result_raises_parse_error(treblle_config, client):
    respx.get(treblle_config.url).mock(return_value=httpx.Response(200, json={"ms": 1}))
    with pytest.raises(ParseError, match="result"):
        SanityBlogExtractor().fetch(treblle_config, client)


@respx.mock
def test_malformed_post_raises_parse_error(treblle_config, client):
    respx.get(treblle_config.url).mock(return_value=httpx.Response(200, json={"result": [{"title": "no slug"}]}))
    with pytest.raises(ParseError):
        SanityBlogExtractor().fetch(treblle_config, client)
