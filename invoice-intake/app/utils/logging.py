from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CustomFormatter(_LOG_FORMAT))
    root.addHandler(handler)
    root.setLevel(level)


class CustomFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.extra_context = getattr(record, "extra_context", "")
        return super().format(record)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonMessage:
    """Helper to build structured, PII-safe log messages."""

    def __init__(self, job_id: str = "", stage: str = "", status: str = "", **kw):
        payload = {"job_id": job_id, "stage": stage, "status": status, **kw}
        self.text = json.dumps(payload, ensure_ascii=False, default=str)

    def __str__(self) -> str:
        return self.text