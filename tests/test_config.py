"""Tests for configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from feedsmith.config import DEFAULT_CONFIG_PATH, load_config
from feedsmith.exceptions import ConfigError, UnknownFeedError


def test_load_default_config_has_expected_feeds():
    config = load_config()
    assert config.ids() == ["boomi", "bump", "kong"]
    boomi = config.get("boomi")
    assert boomi.id == "boomi"
    assert boomi.extractor == "wordpress_api"


def test_default_config_path_points_to_repo_root():
    assert DEFAULT_CONFIG_PATH.name == "feeds.yaml"
    assert DEFAULT_CONFIG_PATH.exists()


def test_get_unknown_feed_raises():
    config = load_config()
    with pytest.raises(UnknownFeedError, match="nope"):
        config.get("nope")


def test_missing_file_raises_config_error(tmp_path: Path):
    with pytest.raises(ConfigError, match="Cannot read"):
        load_config(tmp_path / "missing.yaml")


def test_invalid_yaml_raises_config_error(tmp_path: Path):
    bad = tmp_path / "feeds.yaml"
    bad.write_text("feeds: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError, match="Invalid YAML"):
        load_config(bad)


def test_missing_feeds_key_raises(tmp_path: Path):
    bad = tmp_path / "feeds.yaml"
    bad.write_text("other: 1", encoding="utf-8")
    with pytest.raises(ConfigError, match="top-level 'feeds'"):
        load_config(bad)


def test_feeds_not_mapping_raises(tmp_path: Path):
    bad = tmp_path / "feeds.yaml"
    bad.write_text("feeds:\n  - a\n  - b\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="must be a mapping"):
        load_config(bad)


def test_invalid_feed_entry_raises(tmp_path: Path):
    bad = tmp_path / "feeds.yaml"
    bad.write_text(
        "feeds:\n  x:\n    title: X\n    extractor: wordpress_api\n",  # missing url/site_url
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="Invalid feed configuration"):
        load_config(bad)
