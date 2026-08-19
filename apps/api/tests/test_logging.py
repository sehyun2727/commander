"""Sprint 19 §4.9/§7.3: JSON structured logging + contextvar propagation.

`JSONFormatter` is tested directly against hand-built `LogRecord`s (no
`install_logging()` needed for most cases) so these tests never touch the
process-wide root logger. `install_logging()` itself gets one dedicated
test that saves/restores the root logger's handlers around the mutation.
"""

from __future__ import annotations

import json
import logging

from app.core.logging import (
    JSONFormatter,
    agent_id_var,
    install_logging,
    project_id_var,
    request_id_var,
    task_id_var,
)


def _make_record(msg: str = "hello", **extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="commander.test", level=logging.INFO, pathname=__file__, lineno=1, msg=msg, args=(), exc_info=None
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_formatter_includes_ts_level_logger_msg():
    obj = json.loads(JSONFormatter().format(_make_record("hello world")))
    assert obj["level"] == "INFO"
    assert obj["logger"] == "commander.test"
    assert obj["msg"] == "hello world"
    assert "ts" in obj


def test_formatter_includes_request_id_when_set():
    token = request_id_var.set("req-123")
    try:
        obj = json.loads(JSONFormatter().format(_make_record()))
    finally:
        request_id_var.reset(token)
    assert obj["request_id"] == "req-123"


def test_formatter_omits_request_id_when_not_set():
    assert request_id_var.get() is None
    obj = json.loads(JSONFormatter().format(_make_record()))
    assert "request_id" not in obj


def test_formatter_includes_task_agent_project_id_when_set():
    tokens = (task_id_var.set("task-1"), agent_id_var.set("agent-1"), project_id_var.set("project-1"))
    try:
        obj = json.loads(JSONFormatter().format(_make_record()))
    finally:
        for var, token in zip((task_id_var, agent_id_var, project_id_var), tokens):
            var.reset(token)
    assert obj["task_id"] == "task-1"
    assert obj["agent_id"] == "agent-1"
    assert obj["project_id"] == "project-1"


def test_formatter_omits_task_agent_project_id_when_not_set():
    obj = json.loads(JSONFormatter().format(_make_record()))
    assert "task_id" not in obj
    assert "agent_id" not in obj
    assert "project_id" not in obj


def test_formatter_redacts_secret_shaped_extra_keys():
    record = _make_record(password="hunter2", Authorization="Bearer xyz", api_token="sk-live-abc")
    obj = json.loads(JSONFormatter().format(record))
    assert obj["password"] == "[redacted]"
    assert obj["Authorization"] == "[redacted]"
    # "api_token" isn't an exact match against the blocklist (only "token"
    # is), so it passes through untouched -- this is an exact-key match,
    # not a substring scan.
    assert obj["api_token"] == "sk-live-abc"


def test_formatter_keeps_non_secret_extra_keys():
    record = _make_record(user_email="ceo@test.local", count=3)
    obj = json.loads(JSONFormatter().format(record))
    assert obj["user_email"] == "ceo@test.local"
    assert obj["count"] == 3


def test_formatter_does_not_redact_standard_record_attributes():
    # pathname/lineno/funcName etc. are stock LogRecord attributes, not
    # caller-supplied `extra` -- they must pass through untouched and never
    # trigger the secret-key redaction path.
    record = _make_record()
    obj = json.loads(JSONFormatter().format(record))
    assert "pathname" not in obj
    assert "lineno" not in obj


def test_formatter_includes_exception_traceback():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="commander.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    obj = json.loads(JSONFormatter().format(record))
    assert "exc" in obj
    assert "ValueError: boom" in obj["exc"]


def test_install_logging_replaces_root_handlers_with_json_formatter():
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    try:
        install_logging()
        assert len(root.handlers) == 1
        handler = root.handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert isinstance(handler.formatter, JSONFormatter)
        assert root.level == logging.INFO
    finally:
        root.handlers.clear()
        root.handlers.extend(saved_handlers)
        root.setLevel(saved_level)
