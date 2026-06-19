"""Structured logging setup.

One call to `configure_logging()` at startup wires `structlog` to the settings
module: human-readable console output in dev, JSON when `log_json` is set (for
log aggregation in the pilot). Request and turn instrumentation bind context via
`structlog.contextvars`, so every log line for one request carries its
`request_id` and `thread_id` without threading them through call signatures.
"""

import logging

import structlog

from app.config import settings


def configure_logging() -> None:
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if settings.log_json
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[settings.log_level.upper()]
        ),
        cache_logger_on_first_use=True,
    )
