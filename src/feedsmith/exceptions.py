"""Custom exception hierarchy for feedsmith.

Internal layers raise these; the CLI boundary (``cli.py``) is the only place
that catches :class:`FeedsmithError` and maps it to a process exit code.
"""

from __future__ import annotations


class FeedsmithError(Exception):
    """Base class for all feedsmith errors."""


class ConfigError(FeedsmithError):
    """Raised when ``feeds.yaml`` is missing or invalid."""


class UnknownFeedError(FeedsmithError):
    """Raised when a requested feed id or extractor type is not configured."""


class FetchError(FeedsmithError):
    """Raised when a source blog cannot be fetched over HTTP."""


class ParseError(FeedsmithError):
    """Raised when a fetched response cannot be parsed into posts."""
