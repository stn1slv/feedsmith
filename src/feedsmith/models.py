"""Normalized domain models shared across extractors and the feed builder."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class Post(BaseModel):
    """A single blog post, normalized across all source types."""

    id: str = Field(..., description="Stable unique identifier (used as the Atom entry id).")
    title: str
    url: str = Field(..., description="Canonical link to the post.")
    published: datetime = Field(..., description="Timezone-aware publication timestamp.")
    summary: str | None = None
    author: str | None = None
    categories: list[str] = Field(default_factory=list)

    @field_validator("published")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("published must be timezone-aware")
        return value


class FeedMeta(BaseModel):
    """Metadata describing a generated feed."""

    id: str = Field(..., description="Stable feed identifier (also the Atom feed id).")
    title: str
    site_url: str = Field(..., description="Human-facing blog URL.")
    self_url: str | None = Field(default=None, description="Canonical URL of this feed, if hosted.")
