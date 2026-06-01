"""Tests for the Next.js ``__NEXT_DATA__`` extractor."""

from __future__ import annotations

import httpx
import pytest
import respx

from feedsmith.exceptions import FetchError, ParseError
from feedsmith.extractors.nextjs_blog import NextjsBlogExtractor


@respx.mock
def test_fetch_maps_cards(kong_config, kong_html, client):
    respx.get(kong_config.url).mock(return_value=httpx.Response(200, text=kong_html))
    posts = NextjsBlogExtractor().fetch(kong_config, client)

    assert len(posts) > 0
    first = posts[0]
    assert first.id == "6a0f5e46b33c14000128bd41"
    assert first.title.startswith("Insomnia 12.6")
    assert first.url == "https://konghq.com/blog/product-releases/insomnia-12-6"
    assert first.author == "Juhi Singh"
    assert first.categories == ["Product Releases"]
    assert first.published.year == 2026


@respx.mock
def test_http_error_raises_fetch_error(kong_config, client):
    respx.get(kong_config.url).mock(return_value=httpx.Response(500))
    with pytest.raises(FetchError):
        NextjsBlogExtractor().fetch(kong_config, client)


@respx.mock
def test_missing_next_data_raises_parse_error(kong_config, client):
    respx.get(kong_config.url).mock(return_value=httpx.Response(200, text="<html>no script</html>"))
    with pytest.raises(ParseError, match="__NEXT_DATA__"):
        NextjsBlogExtractor().fetch(kong_config, client)


@respx.mock
def test_unexpected_structure_raises_parse_error(kong_config, client):
    body = '<script id="__NEXT_DATA__" type="application/json">{"props": {}}</script>'
    respx.get(kong_config.url).mock(return_value=httpx.Response(200, text=body))
    with pytest.raises(ParseError, match="structure"):
        NextjsBlogExtractor().fetch(kong_config, client)
