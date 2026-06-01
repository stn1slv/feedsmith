"""Configuration loading for feedsmith.

Feeds are declared in ``feeds.yaml``. Each entry binds a blog id to an extractor
type plus the URLs and limits that extractor needs.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError

from feedsmith.exceptions import ConfigError, UnknownFeedError

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "feeds.yaml"


class FeedConfig(BaseModel):
    """Declarative configuration for a single feed."""

    id: str
    title: str
    extractor: str = Field(..., description="Extractor type name resolved via the registry.")
    url: str = Field(..., description="Source URL the extractor fetches.")
    site_url: str = Field(..., description="Human-facing blog URL for feed metadata.")
    max_items: int = Field(default=20, ge=1, le=200)


class AppConfig(BaseModel):
    """Top-level configuration: a mapping of feed id to its config."""

    feeds: dict[str, FeedConfig]

    def get(self, feed_id: str) -> FeedConfig:
        """Return the config for ``feed_id`` or raise :class:`UnknownFeedError`."""
        try:
            return self.feeds[feed_id]
        except KeyError as err:
            available = ", ".join(sorted(self.feeds)) or "(none)"
            raise UnknownFeedError(f"Unknown feed '{feed_id}'. Available: {available}") from err

    def ids(self) -> list[str]:
        """Return configured feed ids in sorted order."""
        return sorted(self.feeds)


def load_config(path: Path | None = None) -> AppConfig:
    """Load and validate ``feeds.yaml``.

    Args:
        path: Optional override path. Defaults to the repo-root ``feeds.yaml``.

    Raises:
        ConfigError: If the file is missing, malformed, or fails validation.
    """
    config_path = path or DEFAULT_CONFIG_PATH
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as err:
        raise ConfigError(f"Cannot read config file: {config_path}") from err

    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as err:
        raise ConfigError(f"Invalid YAML in {config_path}") from err

    if not isinstance(data, dict) or "feeds" not in data:
        raise ConfigError(f"Config must contain a top-level 'feeds' mapping: {config_path}")

    feeds_raw = data["feeds"]
    if not isinstance(feeds_raw, dict):
        raise ConfigError("'feeds' must be a mapping of id -> feed config")

    # Inject the mapping key as each feed's id so it is available downstream.
    for feed_id, entry in feeds_raw.items():
        if isinstance(entry, dict):
            entry.setdefault("id", feed_id)

    try:
        return AppConfig.model_validate(data)
    except ValidationError as err:
        raise ConfigError(f"Invalid feed configuration in {config_path}:\n{err}") from err
