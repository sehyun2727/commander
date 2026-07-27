from __future__ import annotations

import pytest

from app.core.boot_checks import BootConfigError, redact_database_url, validate_boot_config
from app.core.config import settings


def test_mock_provider_never_requires_a_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "commander_provider", "mock")
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    validate_boot_config()  # must not raise


def test_anthropic_provider_without_a_key_fails_fast(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "commander_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    with pytest.raises(BootConfigError, match="ANTHROPIC_API_KEY"):
        validate_boot_config()


def test_anthropic_provider_with_a_key_passes(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "commander_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-real-key")
    validate_boot_config()  # must not raise


def test_unsupported_database_scheme_fails_fast(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "commander_provider", "mock")
    monkeypatch.setattr(settings, "database_url", "mysql://user:pass@localhost/db")
    with pytest.raises(BootConfigError, match="not a sqlite or postgresql URL"):
        validate_boot_config()


def test_redact_database_url_strips_credentials():
    assert (
        redact_database_url("postgresql+asyncpg://commander:s3cret@localhost:5432/commander")
        == "postgresql+asyncpg://***@localhost:5432/commander"
    )


def test_redact_database_url_leaves_credential_free_urls_alone():
    assert redact_database_url("sqlite+aiosqlite:///./commander.db") == "sqlite+aiosqlite:///./commander.db"
