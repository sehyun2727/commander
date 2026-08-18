from __future__ import annotations

from app.modules.agent_harness.profiles import VALIDATION_PROFILES_BY_NAME, resolve_validation_profile
from app.templates.software_company import TEMPLATE


def test_profiles_match_template_checks_exactly():
    assert set(VALIDATION_PROFILES_BY_NAME) == {check.name for check in TEMPLATE.checks}


def test_resolve_known_profile_returns_the_checkspec():
    profile = resolve_validation_profile("pytest")
    assert profile is not None
    assert profile.name == "pytest"
    assert profile.command == ("python", "-m", "pytest", "-q")


def test_resolve_unknown_profile_returns_none():
    assert resolve_validation_profile("rm -rf /") is None
    assert resolve_validation_profile("not_a_real_profile") is None
