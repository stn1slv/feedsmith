"""Atom feed serialization using feedgen."""

from __future__ import annotations

from datetime import UTC, datetime

from feedgen.feed import FeedGenerator

from feedsmith.models import FeedMeta, Post


def build_atom(meta: FeedMeta, posts: list[Post]) -> str:
    """Render posts as an Atom 1.0 feed.

    Args:
        meta: Feed-level metadata.
        posts: Posts already sorted newest-first by the caller.

    Returns:
        The Atom feed as a pretty-printed XML string.
    """
    fg = FeedGenerator()
    # Atom requires the feed id to be an IRI; the human-facing site URL serves well.
    fg.id(meta.site_url)
    fg.title(meta.title)
    fg.link(href=meta.site_url, rel="alternate")
    if meta.self_url:
        fg.link(href=meta.self_url, rel="self")

    last_updated = max((p.updated or p.published for p in posts), default=datetime.now(UTC))
    fg.updated(last_updated)

    # feedgen prepends entries, so add oldest first to keep newest at the top.
    for post in reversed(posts):
        entry = fg.add_entry()
        entry.id(post.url)
        entry.title(post.title)
        entry.link(href=post.url, rel="alternate")
        entry.published(post.published)
        entry.updated(post.updated or post.published)
        if post.summary:
            entry.summary(post.summary)
        if post.author:
            entry.author(name=post.author)
        for category in post.categories:
            entry.category(term=category)

    atom_bytes: bytes = fg.atom_str(pretty=True)
    return atom_bytes.decode("utf-8")
