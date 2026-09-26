"""Shared HTTP client factory.

Centralizes the User-Agent, timeout, and retry policy so every extractor makes
polite, consistent requests.
"""

from __future__ import annotations

from importlib.metadata import version

import httpx

USER_AGENT = f"feedsmith/{version('feedsmith')} (+https://github.com/stn1slv/feedsmith; Atom feed generator)"
DEFAULT_TIMEOUT = 20.0
DEFAULT_RETRIES = 2


def build_client(
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> httpx.Client:
    """Create an ``httpx.Client`` with sensible defaults for scraping.

    Args:
        timeout: Per-request timeout in seconds.
        retries: Number of connection-level retries on transport errors.

    Returns:
        A configured client. The caller is responsible for closing it.
    """
    transport = httpx.HTTPTransport(retries=retries)
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.9"},
        timeout=timeout,
        follow_redirects=True,
        transport=transport,
    )
