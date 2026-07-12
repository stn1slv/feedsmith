"""Tests for the service orchestration layer."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx
import pytest
import respx

from feedsmith.config import AppConfig
from feedsmith.exceptions import ConfigError, FetchError
from feedsmith.service import generate_all, generate_feed

ATOM = "{http://www.w3.org/2005/Atom}"


@respx.mock
def test_generate_feed_sorts_and_truncates(boomi_config, boomi_json, client):
    boomi_config.max_items = 2
    respx.get(boomi_config.url).mock(return_value=httpx.Response(200, text=boomi_json))

    root = ET.fromstring(generate_feed(boomi_config, client))
    entries = root.findall(f"{ATOM}entry")
    assert len(entries) == 2  # truncated from 3

    published = [e.findtext(f"{ATOM}published") for e in entries]
    assert published == sorted(published, reverse=True)  # newest first


@respx.mock
def test_generate_all_returns_feed_per_config(boomi_config, kong_config, boomi_json, kong_html, client):
    respx.get(boomi_config.url).mock(return_value=httpx.Response(200, text=boomi_json))
    respx.get(kong_config.url).mock(return_value=httpx.Response(200, text=kong_html))
    config = AppConfig(feeds={"boomi": boomi_config, "kong": kong_config})

    feeds = generate_all(config, client)
    assert set(feeds) == {"boomi", "kong"}
    for atom in feeds.values():
        assert atom.startswith("<?xml")


@respx.mock
def test_generate_all_skips_failed_feed_and_continues(books_config, boomi_config, boomi_json, client):
    respx.get(books_config.url).mock(return_value=httpx.Response(503))
    respx.get(boomi_config.url).mock(return_value=httpx.Response(200, text=boomi_json))
    config = AppConfig(feeds={"books": books_config, "boomi": boomi_config})

    feeds = generate_all(config, client)
    assert set(feeds) == {"boomi"}


@respx.mock
def test_generate_feed_raises_on_fetch_error(boomi_config, client):
    respx.get(boomi_config.url).mock(return_value=httpx.Response(500))
    with pytest.raises(FetchError):
        generate_feed(boomi_config, client)


def test_generate_all_raises_on_config_error(books_config, client):
    bad_books = books_config.model_copy(update={"query": None})
    config = AppConfig(feeds={"books": bad_books})
    with pytest.raises(ConfigError):
        generate_all(config, client)
