"""Named validation-profile lookup for the Agent Harness `run_validation`
tool (Sprint 16 §4.3, DECISIONS.md #233).

Reuses `TEMPLATE.checks` (the existing `CheckSpec` tuple:
`python-syntax`, `pytest`, `node-test`) as the canonical registry rather
than inventing a second one -- these are already server-owned, glob-
detected, argv-list commands executed against mission-repository content
inside the sandbox (`workflow_engine.engine._run_checks`), which is
exactly "named profile, bounded params, no free string" (brief §4.3).
The provider selects a profile *name* only; it never supplies a command,
executable, or shell string (Rule #9).
"""

from __future__ import annotations

from ...core.interfaces.sandbox import CheckSpec
from ...templates.software_company import TEMPLATE

VALIDATION_PROFILES_BY_NAME: dict[str, CheckSpec] = {check.name: check for check in TEMPLATE.checks}


def resolve_validation_profile(name: str) -> CheckSpec | None:
    """Return the `CheckSpec` for a provider-selected profile name, or
    `None` if the name is not one of the template's registered checks --
    callers must treat `None` as a denial, never a default profile."""
    return VALIDATION_PROFILES_BY_NAME.get(name)
