"""Immutable per-role contracts — the layer PromptBuilder always appends
LAST, after every personality/working/decision trait and every CEO custom
instruction, so no profile configuration can ever suppress it (see
`builder.build`). This is where the pipeline's parseable output shape
(the Reviewer's trailing Verdict line, and the softer Problem/Recommendation/
Risk/Impact sections before it) is guaranteed to survive.

The contract text itself lives on the active company template
(app/templates) — this module just re-exports it under the name the rest
of prompt_builder already depends on, so template swaps never require a
prompt_builder code change.
"""

from __future__ import annotations

from ...templates import TEMPLATE

ROLE_CONTRACTS: dict[str, str] = TEMPLATE.role_contracts
ENGINEER_CONTRACT_BY_DELIVERABLE: dict[str, str] = TEMPLATE.engineer_contract_by_deliverable
# Tuple order is (PM, Engineer, Reviewer) -- see software_company.py's
# ROLES comment; engine.py relies on the same positional unpacking.
ENGINEER_ROLE_KEY: str = TEMPLATE.roles[1].key
