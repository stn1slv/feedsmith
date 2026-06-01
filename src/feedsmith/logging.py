"""Structured logging configuration using structlog."""

from __future__ import annotations

import logging
import sys
from typing import cast

import structlog


def configure_logging(*, level: int = logging.INFO, json_logs: bool = False) -> None:
    """Configure structlog to emit structured logs to stderr.

    Args:
        level: Standard library logging level.
        json_logs: Emit JSON lines when True, otherwise human-readable console output.
    """
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        # Do not cache: the bound logger captures the current stderr, which must
        # stay current across reconfiguration (and across pytest's stream capture).
        cache_logger_on_first_use=False,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return cast("structlog.stdlib.BoundLogger", structlog.get_logger(name))
