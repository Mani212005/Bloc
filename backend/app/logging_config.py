"""
Structured logging configuration for Bloc CRM.
Emits JSON lines in production and coloured human-readable output in development.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Single-line JSON log records."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Merge any extra fields passed via `extra=` kwarg
        for key, val in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                payload[key] = val
        return json.dumps(payload, default=str)


class _DevFormatter(logging.Formatter):
    _COLOURS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self._COLOURS.get(record.levelname, "")
        prefix = f"{colour}{record.levelname:<8}{self._RESET}"
        base = f"{prefix} [{record.name}] {record.getMessage()}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configure_logging() -> None:
    """Call once at application startup."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    is_json = os.getenv("LOG_FORMAT", "dev").lower() == "json"
    formatter: logging.Formatter = _JsonFormatter() if is_json else _DevFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # Remove existing handlers to avoid duplicate output
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet noisy libraries
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# Module-level loggers used across the app
logger = logging.getLogger("bloc")
assignment_logger = logging.getLogger("bloc.assignment")
webhook_logger = logging.getLogger("bloc.webhook")
