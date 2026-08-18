from __future__ import annotations

from app.modules.agent_harness.output import bound_output, redact_environment_like_content


def test_bound_output_passes_through_short_text():
    text, truncated = bound_output("hello", max_bytes=100)
    assert text == "hello"
    assert truncated is False


def test_bound_output_truncates_long_text():
    text, truncated = bound_output("a" * 200, max_bytes=50)
    assert len(text.encode("utf-8")) <= 50
    assert truncated is True


def test_bound_output_uses_configured_default(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "commander_harness_max_output_bytes", 10)
    text, truncated = bound_output("a" * 100)
    assert truncated is True
    assert len(text.encode("utf-8")) <= 10


def test_redact_environment_like_content_masks_secret_shaped_lines():
    text = "ANTHROPIC_API_KEY=sk-ant-super-secret\nnormal_line=fine\n"
    redacted = redact_environment_like_content(text)
    assert "sk-ant-super-secret" not in redacted
    assert "ANTHROPIC_API_KEY=[redacted]" in redacted
    assert "normal_line=fine" in redacted


def test_redact_environment_like_content_leaves_plain_text_alone():
    text = "def foo():\n    return 1\n"
    assert redact_environment_like_content(text) == text
