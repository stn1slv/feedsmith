"""Extractor protocol and shared helpers."""

from __future__ import annotations

import html
import re
from typing import Protocol, runtime_checkable

import httpx

from feedsmith.config import FeedConfig
from feedsmith.models import Post

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@runtime_checkable
class Extractor(Protocol):
    """A source-specific strategy that produces normalized posts.

    Implementations fetch a single blog and map its response to ``Post`` objects.
    They must not sort or truncate; the service layer handles ordering and limits.
    """

    def fetch(self, cfg: FeedConfig, client: httpx.Client) -> list[Post]:
        """Fetch the blog described by ``cfg`` and return its posts."""
        ...


def clean_text(value: str | None) -> str | None:
    """Strip HTML tags, unescape entities, and collapse whitespace.

    Returns None for input that is empty after cleaning.
    """
    if not value:
        return None
    text = html.unescape(_TAG_RE.sub("", value))
    text = _WS_RE.sub(" ", text).strip()
    return text or None
