"""Tests for the O'Reilly Media books extractor."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from feedsmith.exceptions import FetchError, ParseError
from feedsmith.extractors.oreilly_books import OreillyBooksExtractor, _max_issued


@pytest.fixture(autouse=True)
def _frozen_now(monkeypatch):
    # Freeze the clock so the release-date cutoff is deterministic. With "now" at
    # 2026-06-17, the cutoff is the first instant of next month (2026-07-01): books
    # issued in July 2026 or later are excluded as not-yet-released.
    monkeypatch.setattr(
        "feedsmith.extractors.oreilly_books._now",
        lambda: datetime(2026, 6, 17, tzinfo=UTC),
    )


@respx.mock
def test_fetch_maps_posts(oreilly_config, oreilly_books_json, client):
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, text=oreilly_books_json))
    posts = OreillyBooksExtractor().fetch(oreilly_config, client)

    # Skipped: the future-issued book 1 (Aug 2026), the German, the undated, and the
    # video result; only the released book 2 remains.
    assert [p.id for p in posts] == ["urn:orm:book:9782222222222"]

    # Results come back in source order; the service layer sorts by published desc.
    first = posts[0]
    assert first.title == "Hands-On API Governance"
    assert first.url == "https://www.oreilly.com/library/view/hands-on-api-governance/9782222222222/"
    assert first.author == "Grace Gateway"
    assert first.summary == "An approachable look at API governance."
    assert first.categories == []
    # published is the real release date (issued, the 1st); updated is the catalog-add
    # date (date_added, the 10th).
    assert (first.published.year, first.published.month, first.published.day) == (2026, 6, 1)
    assert first.published.tzinfo == UTC
    assert (first.updated.year, first.updated.month, first.updated.day) == (2026, 6, 10)
    assert first.updated.tzinfo == UTC


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 6, 17, tzinfo=UTC), datetime(2026, 7, 1, tzinfo=UTC)),
        (datetime(2026, 12, 31, tzinfo=UTC), datetime(2027, 1, 1, tzinfo=UTC)),
    ],
)
def test_max_issued_is_first_of_next_month(now, expected):
    assert _max_issued(now) == expected


@respx.mock
def test_future_issued_is_skipped_but_current_month_is_kept(oreilly_config, client):
    # With now frozen at 2026-06-17 (cutoff 2026-07-01): a July release is excluded,
    # a release later in the current month (June 30) is kept.
    payload = {
        "results": [
            {
                "ourn": "urn:orm:book:future",
                "format": "book",
                "language": "en",
                "title": "Future Release",
                "date_added": "2026-06-16T00:00:00Z",
                "issued": "2026-07-01T00:00:00Z",
                "web_url": "/library/view/future/future/",
            },
            {
                "ourn": "urn:orm:book:thismonth",
                "format": "book",
                "language": "en",
                "title": "This Month Release",
                "date_added": "2026-06-16T00:00:00Z",
                "issued": "2026-06-30T00:00:00Z",
                "web_url": "/library/view/thismonth/thismonth/",
            },
        ]
    }
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, json=payload))
    posts = OreillyBooksExtractor().fetch(oreilly_config, client)
    assert [p.id for p in posts] == ["urn:orm:book:thismonth"]


@respx.mock
def test_missing_or_unparseable_issued_is_skipped(oreilly_config, client):
    # Without a usable publication date we cannot tell a released book from a future
    # one, so the result is skipped.
    base = {
        "ourn": "urn:orm:book:base",
        "format": "book",
        "language": "en",
        "title": "Released Book",
        "date_added": "2026-06-10T00:00:00Z",
        "web_url": "/library/view/base/base/",
    }
    payload = {
        "results": [
            base,  # no issued at all
            {**base, "ourn": "urn:orm:book:badissued", "issued": "not-a-date"},
        ]
    }
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, json=payload))
    assert OreillyBooksExtractor().fetch(oreilly_config, client) == []


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

    # At the config-allowed maximum (max_items le=200), the buffer would exceed the
    # API's 200-result ceiling, so the request limit clamps back to 200.
    OreillyBooksExtractor().fetch(oreilly_config.model_copy(update={"max_items": 200}), client)
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
                "issued": "2026-06-05T00:00:00Z",
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
        "issued": "2026-06-05T00:00:00Z",
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
                "issued": "2026-06-05T00:00:00Z",
                "web_url": "/library/view/no-urn/9790000000001/",
            }
        ]
    }
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, json=payload))
    posts = OreillyBooksExtractor().fetch(oreilly_config, client)
    assert [p.id for p in posts] == ["9790000000001"]


@respx.mock
def test_naive_dates_are_stamped_utc(oreilly_config, client):
    # issued and date_added without an offset must still produce tz-aware
    # published and updated timestamps.
    payload = {
        "results": [
            {
                "ourn": "urn:orm:book:naive",
                "format": "book",
                "language": "en",
                "title": "Naive Date Book",
                "date_added": "2026-06-11T09:30:00",
                "issued": "2026-06-05T00:00:00",
                "web_url": "/library/view/naive/naive/",
            }
        ]
    }
    respx.get(oreilly_config.url).mock(return_value=httpx.Response(200, json=payload))
    posts = OreillyBooksExtractor().fetch(oreilly_config, client)
    assert len(posts) == 1
    assert posts[0].published.tzinfo == UTC
    assert posts[0].updated.tzinfo == UTC


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
                "issued": "2026-06-05T00:00:00Z",
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
