"""Tests for the Google Books API extractor."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from feedsmith.exceptions import ConfigError, FetchError, ParseError
from feedsmith.extractors.google_books import GoogleBooksExtractor, _min_published


@pytest.fixture(autouse=True)
def _frozen_now(monkeypatch):
    # Freeze the clock so the rolling recency cutoff is deterministic. With "now"
    # at 2026-07-01, the two-month cutoff is 2026-05-01 (matches the fixture dates).
    monkeypatch.setattr(
        "feedsmith.extractors.google_books._now",
        lambda: datetime(2026, 7, 1, tzinfo=UTC),
    )


@respx.mock
def test_fetch_maps_posts(books_config, google_books_json, client):
    respx.get(books_config.url).mock(return_value=httpx.Response(200, text=google_books_json))
    posts = GoogleBooksExtractor().fetch(books_config, client)

    # Skipped: the pre-cutoff (2026-04-15), German, and undated volumes; 3 remain.
    assert [p.id for p in posts] == ["fullDate001", "yearMonth002", "yearOnly003"]

    # Volumes come back in source order; the service layer sorts by published desc.
    first = posts[0]
    assert first.title == "Mastering MuleSoft: Anypoint Platform in Practice"
    assert first.url == "https://books.google.com/books/about/Mastering_MuleSoft.html?id=fullDate001"
    assert first.author == "Jane Integrator, Sam Connector"
    assert first.categories == ["Computers"]
    # clean_text strips the <b> tag from the description.
    assert first.summary == "A hands-on guide to building integrations on the Anypoint Platform."
    assert first.published.year == 2026
    assert first.published.month == 5
    assert first.published.day == 12
    assert first.published.tzinfo == UTC


@respx.mock
def test_partial_dates_are_padded(books_config, google_books_json, client):
    respx.get(books_config.url).mock(return_value=httpx.Response(200, text=google_books_json))
    posts = GoogleBooksExtractor().fetch(books_config, client)
    by_id = {p.id: p for p in posts}

    # "2026-06" -> 2026-06-01; "2027" -> 2027-01-01.
    assert (by_id["yearMonth002"].published.year, by_id["yearMonth002"].published.month) == (2026, 6)
    assert (by_id["yearOnly003"].published.year, by_id["yearOnly003"].published.month) == (2027, 1)
    # No canonicalVolumeLink -> falls back to infoLink.
    assert by_id["yearMonth002"].url == "https://books.google.com/books?id=yearMonth002"


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
                    "publishedDate": "2026-05-15",
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


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 5, 1, tzinfo=UTC)),
        (datetime(2026, 1, 15, tzinfo=UTC), datetime(2025, 11, 15, tzinfo=UTC)),  # year wrap
        (datetime(2026, 8, 31, tzinfo=UTC), datetime(2026, 6, 30, tzinfo=UTC)),  # day clamp
    ],
)
def test_min_published_is_two_months_before(now, expected):
    assert _min_published(now) == expected


@respx.mock
def test_requests_full_page_regardless_of_max_items(books_config, google_books_json, client):
    # Request the full page (40) so client-side filters don't starve the feed;
    # the service layer truncates to max_items afterward.
    assert books_config.max_items == 20
    route = respx.get(books_config.url).mock(
        return_value=httpx.Response(200, text=google_books_json)
    )
    GoogleBooksExtractor().fetch(books_config, client)
    assert route.calls.last.request.url.params["maxResults"] == "40"


@respx.mock
def test_full_iso_timestamp_is_parsed(books_config, client):
    payload = {
        "items": [
            {
                "id": "iso001",
                "volumeInfo": {
                    "title": "Timestamped Book",
                    "publishedDate": "2026-05-12T00:00:00Z",
                    "language": "en",
                    "canonicalVolumeLink": "https://books.google.com/books?id=iso001",
                },
            }
        ]
    }
    respx.get(books_config.url).mock(return_value=httpx.Response(200, json=payload))
    posts = GoogleBooksExtractor().fetch(books_config, client)
    assert len(posts) == 1
    assert (posts[0].published.year, posts[0].published.month, posts[0].published.day) == (2026, 5, 12)


@respx.mock
def test_books_before_cutoff_are_excluded(books_config, client):
    # The cutoff is inclusive: 2026-05-01 is kept; the day before is dropped.
    payload = {
        "items": [
            {
                "id": "kept",
                "volumeInfo": {
                    "title": "On the Cutoff",
                    "publishedDate": "2026-05-01",
                    "language": "en",
                    "canonicalVolumeLink": "https://books.google.com/books?id=kept",
                },
            },
            {
                "id": "dropped",
                "volumeInfo": {
                    "title": "Day Before the Cutoff",
                    "publishedDate": "2026-04-30",
                    "language": "en",
                    "canonicalVolumeLink": "https://books.google.com/books?id=dropped",
                },
            },
        ]
    }
    respx.get(books_config.url).mock(return_value=httpx.Response(200, json=payload))
    posts = GoogleBooksExtractor().fetch(books_config, client)
    assert [p.id for p in posts] == ["kept"]


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
