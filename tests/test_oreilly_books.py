"""Tests for the O'Reilly Media books extractor."""

from __future__ import annotations

from datetime import UTC

import httpx
import pytest
import respx

from feedsmith.exceptions import FetchError, ParseError
from feedsmith.extractors.oreilly_books import OreillyBooksExtractor


@respx.mock
def test_fetch_maps_posts(oreilly_config, oreilly_books_json, client):
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, text=oreilly_books_json))
    posts = OreillyBooksExtractor().fetch(oreilly_config, client)

    # Skipped: the German, the undated, and the video result; 2 books remain.
    assert [p.id for p in posts] == ["urn:orm:book:9781111111111", "urn:orm:book:9782222222222"]

    # Results come back in source order; the service layer sorts by published desc.
    first = posts[0]
    assert first.title == "Mastering Event-Driven Systems"
    assert first.url == "https://www.oreilly.com/library/view/mastering-event-driven/9781111111111/"
    assert first.author == "Ada Stream, Linus Queue"
    # clean_text strips the HTML tags from the description.
    assert first.summary == "A practical guide to building event-driven systems."
    assert first.categories == []
    # published comes from date_added (16th), not issued (the 25th).
    assert (first.published.year, first.published.month, first.published.day) == (2026, 6, 16)
    assert first.published.tzinfo == UTC


@respx.mock
def test_requests_book_page_with_publisher_filter(oreilly_config, oreilly_books_json, client):
    route = respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, text=oreilly_books_json))
    OreillyBooksExtractor().fetch(oreilly_config, client)
    params = route.calls.last.request.url.params
    assert params["formats"] == "book"
    assert params["publishers"] == "O'Reilly Media, Inc."
    assert params["sort"] == "date_added"
    assert params["order"] == "desc"


@respx.mock
def test_limit_scales_with_max_items_and_is_capped(oreilly_config, oreilly_books_json, client):
    route = respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, text=oreilly_books_json))

    # Requests max_items plus a small buffer for skipped results.
    OreillyBooksExtractor().fetch(oreilly_config.model_copy(update={"max_items": 100}), client)
    assert route.calls.last.request.url.params["limit"] == "110"

    # Capped at the API's 200-result ceiling.
    OreillyBooksExtractor().fetch(oreilly_config.model_copy(update={"max_items": 500}), client)
    assert route.calls.last.request.url.params["limit"] == "200"


@respx.mock
def test_non_string_text_fields_are_tolerated(oreilly_config, client):
    # The API schema promises strings, but guard against junk values rather than
    # crashing the whole feed on one bad result.
    payload = {
        "results": [
            {
                "ourn": "urn:orm:book:junk",
                "format": "book",
                "language": "en",
                "title": "Resilient Book",
                "authors": ["Real Author", 42, None],
                "description": 1234,
                "date_added": "2026-06-15T00:00:00Z",
                "web_url": "/library/view/resilient/junk/",
            }
        ]
    }
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, json=payload))
    posts = OreillyBooksExtractor().fetch(oreilly_config, client)

    assert len(posts) == 1
    assert posts[0].author == "Real Author"  # non-string entries dropped
    assert posts[0].summary is None  # non-string description ignored


@respx.mock
def test_malformed_results_are_skipped_not_fatal(oreilly_config, client):
    # A single bad result must be skipped, never abort the whole feed.
    good = {
        "ourn": "urn:orm:book:good",
        "format": "book",
        "language": "en",
        "title": "Good Book",
        "date_added": "2026-06-10T00:00:00Z",
        "web_url": "/library/view/good/good/",
    }
    payload = {
        "results": [
            "not-a-dict",  # not a mapping
            {**good, "ourn": None, "archive_id": None, "isbn": None},  # no usable id
            {**good, "title": None},  # missing title
            {**good, "web_url": None},  # missing link
            {**good, "date_added": None},  # missing date
            good,
        ]
    }
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, json=payload))
    posts = OreillyBooksExtractor().fetch(oreilly_config, client)
    assert [p.id for p in posts] == ["urn:orm:book:good"]


@respx.mock
def test_id_falls_back_to_archive_id_then_isbn(oreilly_config, client):
    payload = {
        "results": [
            {
                "archive_id": "9790000000001",
                "format": "book",
                "language": "en",
                "title": "No URN Book",
                "date_added": "2026-06-12T00:00:00Z",
                "web_url": "/library/view/no-urn/9790000000001/",
            }
        ]
    }
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, json=payload))
    posts = OreillyBooksExtractor().fetch(oreilly_config, client)
    assert [p.id for p in posts] == ["9790000000001"]


@respx.mock
def test_naive_date_added_is_stamped_utc(oreilly_config, client):
    # A date_added without an offset must still produce a tz-aware published.
    payload = {
        "results": [
            {
                "ourn": "urn:orm:book:naive",
                "format": "book",
                "language": "en",
                "title": "Naive Date Book",
                "date_added": "2026-06-11T09:30:00",
                "web_url": "/library/view/naive/naive/",
            }
        ]
    }
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, json=payload))
    posts = OreillyBooksExtractor().fetch(oreilly_config, client)
    assert len(posts) == 1
    assert posts[0].published.tzinfo == UTC


@respx.mock
def test_unparseable_date_is_skipped(oreilly_config, client):
    payload = {
        "results": [
            {
                "ourn": "urn:orm:book:baddate",
                "format": "book",
                "language": "en",
                "title": "Bad Date Book",
                "date_added": "not-a-date",
                "web_url": "/library/view/baddate/baddate/",
            }
        ]
    }
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, json=payload))
    assert OreillyBooksExtractor().fetch(oreilly_config, client) == []


@respx.mock
def test_empty_results_return_no_posts(oreilly_config, client):
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, json={"results": [], "total": 0}))
    assert OreillyBooksExtractor().fetch(oreilly_config, client) == []


@respx.mock
def test_http_error_raises_fetch_error(oreilly_config, client):
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(503))
    with pytest.raises(FetchError):
        OreillyBooksExtractor().fetch(oreilly_config, client)


@respx.mock
def test_non_json_raises_parse_error(oreilly_config, client):
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, text="<html>nope"))
    with pytest.raises(ParseError):
        OreillyBooksExtractor().fetch(oreilly_config, client)


@respx.mock
def test_non_object_payload_raises_parse_error(oreilly_config, client):
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, json=["not", "an", "object"]))
    with pytest.raises(ParseError, match="object"):
        OreillyBooksExtractor().fetch(oreilly_config, client)


@respx.mock
def test_results_not_a_list_raises_parse_error(oreilly_config, client):
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, json={"results": "nope"}))
    with pytest.raises(ParseError, match="results"):
        OreillyBooksExtractor().fetch(oreilly_config, client)
