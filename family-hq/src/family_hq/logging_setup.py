"""Logging: stdlib logging, plain text by default, JSON lines optionally.

Rule (decision D14): log calls pass ids, counts and event names as `extra`. Never titles,
descriptions, notes or project names.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from family_hq.config import LoggingSection

_STANDARD = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


def _extras(record: logging.LogRecord) -> dict[str, object]:
    return {k: v for k, v in record.__dict__.items() if k not in _STANDARD}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            **_extras(record),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class KeyValueFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        stamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        base = f"{stamp} {record.levelname:<7} {record.getMessage()}"
        extras = " ".join(f"{k}={v}" for k, v in _extras(record).items())
        text = f"{base} {extras}".rstrip()
        if record.exc_info:
            text += "\n" + self.formatException(record.exc_info)
        return text


def configure_logging(section: LoggingSection, base_dir_resolver=None) -> None:  # type: ignore[no-untyped-def]
    formatter: logging.Formatter = JsonFormatter() if section.json_format else KeyValueFormatter()
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if section.file is not None:
        path = base_dir_resolver(section.file) if base_dir_resolver else section.file
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(path, encoding="utf-8"))
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    for handler in handlers:
        handler.setFormatter(formatter)
        root.addHandler(handler)
    root.setLevel(section.level.upper())
    for noisy in ("sqlalchemy.engine", "alembic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
