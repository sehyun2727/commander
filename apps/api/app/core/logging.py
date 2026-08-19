"""Structured JSON logging with correlation-ID context propagation.

Two independent ID scopes rather than one unified correlation ID (Sprint
19 §4.9): `request_id_var` lives for one HTTP request (set by the
correlation-ID middleware in main.py); `task_id_var`/`agent_id_var`/
`project_id_var` live for the duration of a background Mission pipeline
(set by workflow_engine around `_spawn`/`_run_role`/
`_run_engineer_tool_loop`). Contextvars propagate through
`asyncio.create_task`, so a log call from deep inside either scope picks
up whichever vars are currently set with no plumbing.

No new logging dependency (no structlog, no python-json-logger) -- this
formatter is code Commander owns.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
task_id_var: ContextVar[str | None] = ContextVar("task_id", default=None)
agent_id_var: ContextVar[str | None] = ContextVar("agent_id", default=None)
project_id_var: ContextVar[str | None] = ContextVar("project_id", default=None)

# Defensive redaction: even if a caller passes a secret-shaped key via
# `logger.info(..., extra={...})`, it never reaches stdout in the clear.
_SECRET_KEYS = frozenset({"password", "token", "key", "secret", "authorization", "cookie"})

_CONTEXTVARS = (
    (request_id_var, "request_id"),
    (task_id_var, "task_id"),
    (agent_id_var, "agent_id"),
    (project_id_var, "project_id"),
)

# Every attribute a stock LogRecord carries -- anything beyond this set on
# record.__dict__ came from a caller's `extra={...}` and is a candidate for
# secret-key redaction.
_STANDARD_RECORD_KEYS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for var, key in _CONTEXTVARS:
            value = var.get()
            if value is not None:
                obj[key] = value
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_KEYS:
                continue
            obj[key] = "[redacted]" if key.lower() in _SECRET_KEYS else value
        return json.dumps(obj, ensure_ascii=False, default=str)


def install_logging() -> None:
    """Replaces the root logger's handlers with one JSON stream handler.
    Existing `logging.getLogger("commander.*")` call sites need no change
    -- they propagate to root and inherit this formatter automatically."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
