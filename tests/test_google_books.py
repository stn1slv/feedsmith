"""Tests for the Google Books API extractor."""

from __future__ import annotations

from datetime import UTC

import httpx
import pytest
import respx

from feedsmith.exceptions import ConfigError, FetchError, ParseError
from feedsmith.extractors.google_books import GoogleBooksExtractor


@respx.mock
def test_fetch_maps_posts(books_config, google_books_json, client):
    respx.get(books_config.url).mock(return_value=httpx.Response(200, text=google_books_json))
    posts = GoogleBooksExtractor().fetch(books_config, client)

    # The German volume and the undated volume are skipped; 3 remain.
    assert [p.id for p in posts] == ["fullDate001", "yearOnly002", "yearMonth003"]

    # Volumes come back in source order; the service layer sorts by published desc.
    first = posts[0]
    assert first.title == "Mastering MuleSoft: Anypoint Platform in Practice"
    assert first.url == "https://books.google.com/books/about/Mastering_MuleSoft.html?id=fullDate001"
    assert first.author == "Jane Integrator, Sam Connector"
    assert first.categories == ["Computers"]
    # clean_text strips the <b> tag from the description.
    assert first.summary == "A hands-on guide to building integrations on the Anypoint Platform."
    assert first.published.year == 2025
    assert first.published.month == 3
    assert first.published.day == 12
    assert first.published.tzinfo == UTC


@respx.mock
def test_partial_dates_are_padded(books_config, google_books_json, client):
    respx.get(books_config.url).mock(return_value=httpx.Response(200, text=google_books_json))
    posts = GoogleBooksExtractor().fetch(books_config, client)
    by_id = {p.id: p for p in posts}

    # "2024" -> 2024-01-01; "2023-09" -> 2023-09-01.
    assert (by_id["yearOnly002"].published.year, by_id["yearOnly002"].published.month) == (2024, 1)
    assert (by_id["yearMonth003"].published.year, by_id["yearMonth003"].published.month) == (2023, 9)
    # No canonicalVolumeLink -> falls back to infoLink.
    assert by_id["yearOnly002"].url == "https://books.google.com/books?id=yearOnly002"


@respx.mock
def test_non_string_text_fields_are_tolerated(books_config, client):
    # The API schema promises strings, but guard against junk values rather than
    # crashing the whole feed on one bad volume.
    payload = {
        "items": [
            {
                "id": "junk001",
                "volumeInfo": {
                    "title": "Resilient Book",
                    "publishedDate": "2025-02-01",
                    "language": "en",
                    "authors": ["Real Author", 42, None],
                    "categories": ["Computers", 7, None],
                    "description": 1234,
                    "canonicalVolumeLink": "https://books.google.com/books?id=junk001",
                },
            }
        ]
    }
    respx.get(books_config.url).mock(return_value=httpx.Response(200, json=payload))
    posts = GoogleBooksExtractor().fetch(books_config, client)

    assert len(posts) == 1
    assert posts[0].author == "Real Author"  # non-string entries dropped
    assert posts[0].categories == ["Computers"]  # non-string entries dropped
    assert posts[0].summary is None  # non-string description ignored


@respx.mock
def test_api_key_sent_when_env_set(books_config, google_books_json, client, monkeypatch):
    monkeypatch.setenv("GOOGLE_BOOKS_API_KEY", "secret-key")
    route = respx.get(books_config.url).mock(return_value=httpx.Response(200, text=google_books_json))
    GoogleBooksExtractor().fetch(books_config, client)
    assert route.calls.last.request.url.params["key"] == "secret-key"


@respx.mock
def test_api_key_omitted_when_env_unset(books_config, google_books_json, client, monkeypatch):
    monkeypatch.delenv("GOOGLE_BOOKS_API_KEY", raising=False)
    route = respx.get(books_config.url).mock(return_value=httpx.Response(200, text=google_books_json))
    GoogleBooksExtractor().fetch(books_config, client)
    assert "key" not in route.calls.last.request.url.params


@respx.mock
def test_empty_results_return_no_posts(books_config, client):
    respx.get(books_config.url).mock(return_value=httpx.Response(200, json={"kind": "books#volumes", "totalItems": 0}))
    assert GoogleBooksExtractor().fetch(books_config, client) == []


def test_missing_query_raises_config_error(books_config, client):
    cfg = books_config.model_copy(update={"query": None})
    with pytest.raises(ConfigError, match="requires a 'query'"):
        GoogleBooksExtractor().fetch(cfg, client)


@respx.mock
def test_http_error_raises_fetch_error(books_config, client):
    respx.get(books_config.url).mock(return_value=httpx.Response(503))
    with pytest.raises(FetchError):
        GoogleBooksExtractor().fetch(books_config, client)


@respx.mock
def test_non_json_raises_parse_error(books_config, client):
    respx.get(books_config.url).mock(return_value=httpx.Response(200, text="<html>nope"))
    with pytest.raises(ParseError):
        GoogleBooksExtractor().fetch(books_config, client)


@respx.mock
def test_non_object_payload_raises_parse_error(books_config, client):
    respx.get(books_config.url).mock(return_value=httpx.Response(200, json=["not", "an", "object"]))
    with pytest.raises(ParseError, match="object"):
        GoogleBooksExtractor().fetch(books_config, client)


@respx.mock
def test_items_not_a_list_raises_parse_error(books_config, client):
    respx.get(books_config.url).mock(return_value=httpx.Response(200, json={"items": "nope"}))
    with pytest.raises(ParseError, match="items"):
        GoogleBooksExtractor().fetch(books_config, client)
