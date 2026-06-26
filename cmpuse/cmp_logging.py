import logging
import os
import re
import sys
from typing import Any, Dict


SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*([^\s,]+)"),
]


def redact_secrets(text: str) -> str:
    if not text:
        return text
    redacted = text
    for pat in SECRET_PATTERNS:
        redacted = pat.sub(lambda m: f"{m.group(1)}=***REDACTED***", redacted)
    return redacted


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        return redact_secrets(msg)


def setup_logging(level: str | int = "INFO") -> None:
    lvl = logging.getLevelName(level) if isinstance(level, str) else level
    handler = logging.StreamHandler(sys.stdout)
    fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    handler.setFormatter(RedactingFormatter(fmt))
    root = logging.getLogger()
    root.setLevel(lvl)
    # Replace existing handlers to avoid duplicates
    root.handlers = [handler]


def event_log(logger: logging.Logger, event: str, **fields: Any) -> None:
    safe_fields: Dict[str, Any] = {}
    for k, v in fields.items():
        if isinstance(v, str):
            safe_fields[k] = redact_secrets(v)
        else:
            safe_fields[k] = v
    logger.info("%s | %s", event, safe_fields)

