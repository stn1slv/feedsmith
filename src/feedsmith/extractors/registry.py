"""Registry mapping extractor type names to implementations."""

from __future__ import annotations

from feedsmith.exceptions import UnknownFeedError
from feedsmith.extractors.base import Extractor
from feedsmith.extractors.bump_blog import BumpBlogExtractor
from feedsmith.extractors.google_books import GoogleBooksExtractor
from feedsmith.extractors.nextjs_blog import NextjsBlogExtractor
from feedsmith.extractors.oreilly_books import OreillyBooksExtractor
from feedsmith.extractors.sanity_blog import SanityBlogExtractor
from feedsmith.extractors.wordpress_api import WordPressApiExtractor

_REGISTRY: dict[str, Extractor] = {
    "wordpress_api": WordPressApiExtractor(),
    "nextjs_blog": NextjsBlogExtractor(),
    "bump_blog": BumpBlogExtractor(),
    "sanity_blog": SanityBlogExtractor(),
    "google_books": GoogleBooksExtractor(),
    "oreilly_books": OreillyBooksExtractor(),
}


def get_extractor(name: str) -> Extractor:
    """Return the extractor registered under ``name``.

    Raises:
        UnknownFeedError: If no extractor is registered for ``name``.
    """
    try:
        return _REGISTRY[name]
    except KeyError as err:
        available = ", ".join(sorted(_REGISTRY))
        raise UnknownFeedError(f"Unknown extractor '{name}'. Available: {available}") from err
