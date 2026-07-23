"""Utility functions and logging configuration."""

from __future__ import annotations

import structlog


def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging for doc-agent."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.get_level_from_name(level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a named logger instance."""
    return structlog.get_logger(name)
