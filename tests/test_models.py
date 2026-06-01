"""Tests for normalized domain models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from feedsmith.models import Post


def test_post_requires_timezone_aware_published():
    with pytest.raises(ValidationError, match="timezone-aware"):
        Post(
            id="1",
            title="t",
            url="https://example.com/p",
            published=datetime(2026, 1, 1, 0, 0),  # naive
        )


def test_post_defaults():
    post = Post(
        id="1",
        title="t",
        url="https://example.com/p",
        published=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert post.summary is None
    assert post.author is None
    assert post.categories == []
