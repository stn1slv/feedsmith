"""Command-line interface (presentation layer).

This is the only boundary that catches :class:`FeedsmithError`, logs it, and
exits with a non-zero status. Internal layers let errors propagate.
"""

from __future__ import annotations

import logging
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Annotated

import typer

from feedsmith.config import load_config
from feedsmith.exceptions import FeedsmithError
from feedsmith.http import build_client
from feedsmith.logging import configure_logging, get_logger
from feedsmith.service import generate_all, generate_feed

app = typer.Typer(
    help="Generate Atom feeds for blogs that publish no official feed.",
    no_args_is_help=True,
    add_completion=False,
)
logger = get_logger("feedsmith.cli")

ConfigOption = Annotated[
    Path | None,
    typer.Option("--config", "-c", help="Path to feeds.yaml (defaults to the bundled config)."),
]
VerboseOption = Annotated[bool, typer.Option("--verbose", "-v", help="Enable debug logging.")]


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"feedsmith {_pkg_version('feedsmith')}")
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Generate Atom feeds for blogs that publish no official feed."""


@app.command("list")
def list_feeds(config: ConfigOption = None, verbose: VerboseOption = False) -> None:
    """List configured feed ids."""
    configure_logging(level=logging.DEBUG if verbose else logging.INFO)
    with _handle_errors():
        app_config = load_config(config)
        for feed_id in app_config.ids():
            cfg = app_config.feeds[feed_id]
            typer.echo(f"{feed_id}\t{cfg.title}\t({cfg.extractor})")


@app.command()
def generate(
    feed_id: Annotated[str, typer.Argument(help="Configured feed id, e.g. 'boomi'.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write Atom to this file instead of stdout."),
    ] = None,
    config: ConfigOption = None,
    verbose: VerboseOption = False,
) -> None:
    """Generate the Atom feed for a single blog."""
    configure_logging(level=logging.DEBUG if verbose else logging.INFO)
    with _handle_errors():
        app_config = load_config(config)
        cfg = app_config.get(feed_id)
        with build_client() as client:
            atom = generate_feed(cfg, client)
        _write(atom, output)


@app.command("generate-all")
def generate_all_cmd(
    output_dir: Annotated[
        Path,
        typer.Option("--output", "-o", help="Directory to write <id>.xml files into."),
    ],
    config: ConfigOption = None,
    verbose: VerboseOption = False,
) -> None:
    """Generate Atom feeds for every configured blog into a directory."""
    configure_logging(level=logging.DEBUG if verbose else logging.INFO)
    with _handle_errors():
        app_config = load_config(config)
        output_dir.mkdir(parents=True, exist_ok=True)
        with build_client() as client:
            feeds = generate_all(app_config, client)
        for feed_id, atom in feeds.items():
            (output_dir / f"{feed_id}.xml").write_text(atom, encoding="utf-8")
            typer.echo(f"wrote {output_dir / f'{feed_id}.xml'}")


def _write(atom: str, output: Path | None) -> None:
    if output is None:
        typer.echo(atom)
    else:
        output.write_text(atom, encoding="utf-8")
        typer.echo(f"wrote {output}")


class _handle_errors:  # noqa: N801 - context manager used like a function
    """Translate FeedsmithError into a clean CLI failure with exit code 1."""

    def __enter__(self) -> _handle_errors:
        return self

    def __exit__(self, exc_type: object, exc: BaseException | None, tb: object) -> None:
        # Returning None never suppresses; non-FeedsmithError exceptions propagate.
        if isinstance(exc, FeedsmithError):
            logger.error("command.failed", error=str(exc), error_type=type(exc).__name__)
            raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
