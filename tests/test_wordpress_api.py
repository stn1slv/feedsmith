"""Tests for the WordPress REST API extractor."""

from __future__ import annotations

from datetime import UTC

import httpx
import pytest
import respx

from feedsmith.exceptions import FetchError, ParseError
from feedsmith.extractors.wordpress_api import WordPressApiExtractor


@respx.mock
def test_fetch_maps_posts(boomi_config, boomi_json, client):
    respx.get(boomi_config.url).mock(return_value=httpx.Response(200, text=boomi_json))
    posts = WordPressApiExtractor().fetch(boomi_config, client)

    assert len(posts) == 3
    first = posts[0]
    assert first.id == "50462"
    assert first.title == "Overview of Data Flows with Boomi"
    assert first.published.tzinfo == UTC
    assert str(first.url).startswith("https://boomi.com/")


@respx.mock
def test_empty_excerpt_becomes_none(boomi_config, boomi_json, client):
    respx.get(boomi_config.url).mock(return_value=httpx.Response(200, text=boomi_json))
    posts = WordPressApiExtractor().fetch(boomi_config, client)
    assert posts[0].summary is None  # fixture's first excerpt is empty


@respx.mock
def test_http_error_raises_fetch_error(boomi_config, client):
    respx.get(boomi_config.url).mock(return_value=httpx.Response(503))
    with pytest.raises(FetchError):
        WordPressApiExtractor().fetch(boomi_config, client)


@respx.mock
def test_non_json_raises_parse_error(boomi_config, client):
    respx.get(boomi_config.url).mock(return_value=httpx.Response(200, text="<html>nope"))
    with pytest.raises(ParseError):
        WordPressApiExtractor().fetch(boomi_config, client)


@respx.mock
def test_non_array_raises_parse_error(boomi_config, client):
    respx.get(boomi_config.url).mock(return_value=httpx.Response(200, json={"not": "a list"}))
    with pytest.raises(ParseError):
        WordPressApiExtractor().fetch(boomi_config, client)


@respx.mock
def test_malformed_post_raises_parse_error(boomi_config, client):
    respx.get(boomi_config.url).mock(return_value=httpx.Response(200, json=[{"id": 1}]))
    with pytest.raises(ParseError):
        WordPressApiExtractor().fetch(boomi_config, client)
