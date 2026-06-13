"""Tests for the Typer CLI boundary."""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import respx
from typer.testing import CliRunner

from feedsmith.cli import app

runner = CliRunner()


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert re.match(r"feedsmith \d+\.\d+\.\d+", result.stdout.strip())


def test_list_command():
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "boomi" in result.stdout
    assert "kong" in result.stdout


@respx.mock
def test_generate_to_stdout(boomi_config, boomi_json):
    respx.get(boomi_config.url).mock(return_value=httpx.Response(200, text=boomi_json))
    result = runner.invoke(app, ["generate", "boomi"])
    assert result.exit_code == 0
    assert "<feed" in result.stdout


@respx.mock
def test_generate_to_file(boomi_config, boomi_json, tmp_path: Path):
    respx.get(boomi_config.url).mock(return_value=httpx.Response(200, text=boomi_json))
    out = tmp_path / "boomi.xml"
    result = runner.invoke(app, ["generate", "boomi", "-o", str(out)])
    assert result.exit_code == 0
    assert out.read_text(encoding="utf-8").startswith("<?xml")


def test_unknown_feed_exits_nonzero():
    result = runner.invoke(app, ["generate", "does-not-exist"])
    assert result.exit_code == 1


@respx.mock
def test_generate_all(
    boomi_config,
    kong_config,
    bump_config,
    treblle_config,
    books_config,
    boomi_json,
    kong_html,
    bump_html,
    treblle_json,
    google_books_json,
    tmp_path: Path,
):
    respx.get(boomi_config.url).mock(return_value=httpx.Response(200, text=boomi_json))
    respx.get(kong_config.url).mock(return_value=httpx.Response(200, text=kong_html))
    respx.get(bump_config.url).mock(return_value=httpx.Response(200, text=bump_html))
    respx.get(treblle_config.url).mock(return_value=httpx.Response(200, text=treblle_json))
    # All books-* feeds share the Google Books URL; one mock covers them.
    respx.get(books_config.url).mock(return_value=httpx.Response(200, text=google_books_json))
    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["generate-all", "-o", str(out_dir)])
    assert result.exit_code == 0
    assert (out_dir / "boomi.xml").exists()
    assert (out_dir / "kong.xml").exists()
    assert (out_dir / "bump.xml").exists()
    assert (out_dir / "treblle.xml").exists()
    assert (out_dir / "books-mulesoft.xml").exists()
