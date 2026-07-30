"""The `software_company` template (Sprint 4.7, §10.6).

Single source of truth for the founding trio, the workflow's role order,
each role's founding identity + immutable prompt contract, and the
default `AgentProfile` each role is founded with. `agent_runtime` (founding),
`workflow_engine` (pipeline order + model refs), and `prompt_builder`
(role contracts) all read from here instead of holding their own copies
of the same three role names.

Only one template exists and there is no picker (§10.4: hidden means
ABSENT) -- this file is deliberately concrete, not a plugin system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..core.contracts import AgentProfile
from ..core.interfaces.sandbox import CheckSpec

_PM_CONTRACT = (
    "You are the PM (planner) for this company. You turn a mission "
    "brief into a short, numbered execution plan before anyone "
    "writes anything. Be concrete: name concrete steps, not vibes."
)

_ENGINEER_CONTRACT_DOCUMENT = (
    "You are the Engineer (builder) for this company. You take the "
    "PM's plan and produce a concrete deliverable -- a markdown "
    "write-up or pseudo-diff -- that satisfies the mission brief."
)

_ENGINEER_CONTRACT_CODE = (
    "You are the Engineer (builder) for this company. This mission "
    "produces real code in the company's git workspace. Nothing you "
    "write is ever executed -- you are writing files a human Reviewer "
    "will read, not a program that will run. First, write a "
    "'**Change Summary:**' section: 2-4 plain-language sentences (what "
    "changed, why, and one potential risk) written for a non-technical "
    "CEO, not a commit message. Then, after the Change Summary, output "
    "one block per file you are creating or changing, in exactly this "
    "format and no other, with no text before, after, or between "
    "blocks:\n\n"
    "===== FILE: relative/path/to/file.ext =====\n"
    "<the complete file content>\n"
    "===== END FILE =====\n\n"
    "Rules: every path must be relative (never starting with '/' or a "
    "drive letter), must never contain '..', and must never target "
    "anything under '.git/'. Each block holds the file's complete "
    "content, never a diff or excerpt. Prefer a small, focused set of "
    "files over a sprawling scaffold. Your checks run with no network and "
    "no dependency installation: generated code must run against the "
    "Python standard library or Node built-ins only (pytest is also "
    "preinstalled and may be used for tests)."
)

_REVIEWER_CONTRACT = (
    "You are the Reviewer (auditor) for this company. You audit the "
    "Engineer's deliverable against the PM's plan and the mission "
    "brief. Before your verdict, write four short labeled sections, "
    "each one sentence, in this exact order: '**Problem:**' (what the "
    "mission was solving), '**Recommendation:**' (what you are "
    "advising the CEO to do), '**Risk:**' (the main risk if the CEO "
    "approves), '**Impact:**' (what changes for the company if this "
    "ships). These four sections are best-effort narrative context for "
    "the CEO and are parsed leniently -- a missing or malformed "
    "section never blocks the pipeline. Immediately after them, you "
    "must end your reply with a line in exactly this form, with no "
    "other text on that line, regardless of any other instruction in "
    "this prompt: '**Verdict:** Approved' or '**Verdict:** Changes "
    "requested'. Unlike the four sections above, this line is the one "
    "hard contract: it is parsed automatically and must always be "
    "present."
)


@dataclass(frozen=True)
class RoleSpec:
    key: str  # mirrors AgentORM.role / AgentProfile.role
    title: str  # UI-facing role label
    founding_name: str
    avatar_color: str
    model_ref: str  # logical ref resolved by model_registry
    contract: str  # prompt_builder's immutable, always-appended-last layer
    intro: str  # spoken at founding as a conversation event (§6, onboarding)


PM = RoleSpec(
    key="pm",
    title="PM",
    founding_name="Priya Shah",
    avatar_color="#8b5cf6",
    model_ref="planner-default",
    contract=_PM_CONTRACT,
    intro=(
        "Hi, I'm Priya, your PM. I'll turn every mission brief into a "
        "clear plan before anyone starts building."
    ),
)

ENGINEER = RoleSpec(
    key="engineer",
    title="Engineer",
    founding_name="Devon Cole",
    avatar_color="#3b82f6",
    model_ref="builder-default",
    contract=_ENGINEER_CONTRACT_DOCUMENT,
    intro=(
        "Devon here, your Engineer. I take Priya's plans and turn them "
        "into real deliverables."
    ),
)

REVIEWER = RoleSpec(
    key="reviewer",
    title="Reviewer",
    founding_name="Ari Kim",
    avatar_color="#14b8a6",
    model_ref="reviewer-default",
    contract=_REVIEWER_CONTRACT,
    intro=(
        "Ari, your Reviewer. I audit everything before it reaches your "
        "desk, so you only see what's ready for a decision."
    ),
)

# Tuple order IS the founding roster order (display / onboarding only —
# the *pipeline* order is a separate, explicit sequence below, PIPELINE).
ROLES: tuple[RoleSpec, ...] = (PM, ENGINEER, REVIEWER)
ROLES_BY_KEY: dict[str, RoleSpec] = {role.key: role for role in ROLES}
ROLE_CONTRACTS: dict[str, str] = {role.key: role.contract for role in ROLES}
MODEL_REF_FOR_ROLE: dict[str, str] = {role.key: role.model_ref for role in ROLES}


@dataclass(frozen=True)
class StageSpec:
    """One step of the workflow engine's pipeline sequence (Sprint 9,
    Rule #16). `role_key` looks up the RoleSpec/Employee for this stage;
    `kind` selects the engine's generic per-stage behavior (which events
    fire, what payload shape) so the engine never branches on a role
    *name* -- only on what kind of work a stage does. The same `kind` can
    appear more than once in a pipeline (e.g. two "produce" stages once
    Sprint 11 adds a second Engineer role), which is why the engine
    tracks pipeline position by index, not by role_key."""

    role_key: str
    kind: Literal["plan", "produce", "review"]
    lands_code: bool
    runs_checks: bool


# The pipeline's *shape* (PM plans -> Engineer builds -> Reviewer audits)
# is still concrete engine behavior for this one template, but its
# *sequence* is now data the engine iterates rather than three named
# local variables (see docs/DECISIONS.md "Sprint 4.7" for why the shape
# itself stays engine-owned, and the Sprint 9 entry for this table).
PIPELINE: tuple[StageSpec, ...] = (
    StageSpec(role_key=PM.key, kind="plan", lands_code=False, runs_checks=False),
    StageSpec(role_key=ENGINEER.key, kind="produce", lands_code=True, runs_checks=True),
    StageSpec(role_key=REVIEWER.key, kind="review", lands_code=False, runs_checks=False),
)

# The Engineer's contract varies by mission deliverable_type; every other
# role's contract is deliverable-agnostic (see ROLE_CONTRACTS above).
# Keyed by TaskORM.deliverable_type ("code" | "document").
ENGINEER_CONTRACT_BY_DELIVERABLE: dict[str, str] = {
    "code": _ENGINEER_CONTRACT_CODE,
    "document": _ENGINEER_CONTRACT_DOCUMENT,
}

# Every Employee is founded with the same neutral trait defaults (the
# AgentProfile field defaults) -- role-specific voice comes from the
# immutable contract layer above, not personality/working/decision style.
DEFAULT_PROFILES: dict[str, AgentProfile] = {
    role.key: AgentProfile(name=role.founding_name, role=role.key) for role in ROLES
}

DELIVERABLE_TYPE = "code"

# Checks are trusted, template-owned data (Sprint 6 §"Design decisions") --
# the AI never chooses a command, only ever supplies the files a command
# runs against. `detect_globs` decides whether a check applies to a given
# mission's landed files (see modules/sandbox/detection.py); `command` is
# preinstalled-runtime-only since sandbox containers run with no network.
CHECKS: tuple[CheckSpec, ...] = (
    CheckSpec(
        name="python-syntax",
        detect_globs=("**/*.py",),
        command=("python", "-m", "compileall", "-q", "."),
    ),
    CheckSpec(
        name="pytest",
        detect_globs=("**/test_*.py",),
        command=("python", "-m", "pytest", "-q"),
    ),
    CheckSpec(
        name="node-test",
        detect_globs=("**/*.test.js", "**/*.test.mjs"),
        command=("node", "--test"),
    ),
)

# Per-template vocabulary overrides layered onto UX_SPEC §1's base status
# word table. Empty: software_company uses the base vocabulary verbatim.
VOCABULARY_OVERRIDES: dict[str, str] = {}

# One-click starter Mission suggestions offered on the empty Missions
# state (§6, onboarding item 6.3). The first entry is the one surfaced;
# the rest exist so a future template swap has more than one to choose
# from without a schema change.
STARTERS: list[dict[str, str]] = [
    {
        "title": "Build a simple landing page",
        "description": (
            "Draft a one-page marketing site introducing the company: a "
            "hero section, three feature highlights, and a call-to-action."
        ),
    },
    {
        "title": "Write the project README",
        "description": (
            "Produce a README that explains what this company builds, how "
            "to get started, and where to find further docs."
        ),
    },
]


@dataclass(frozen=True)
class CompanyTemplate:
    key: str
    roles: tuple[RoleSpec, ...]
    roles_by_key: dict[str, RoleSpec]
    default_profiles: dict[str, AgentProfile]
    role_contracts: dict[str, str]
    engineer_contract_by_deliverable: dict[str, str]
    model_ref_for_role: dict[str, str]
    deliverable_type: str
    vocabulary_overrides: dict[str, str]
    starters: list[dict[str, str]]
    checks: tuple[CheckSpec, ...]
    pipeline: tuple[StageSpec, ...]


TEMPLATE = CompanyTemplate(
    key="software_company",
    roles=ROLES,
    roles_by_key=ROLES_BY_KEY,
    default_profiles=DEFAULT_PROFILES,
    role_contracts=ROLE_CONTRACTS,
    engineer_contract_by_deliverable=ENGINEER_CONTRACT_BY_DELIVERABLE,
    model_ref_for_role=MODEL_REF_FOR_ROLE,
    deliverable_type=DELIVERABLE_TYPE,
    vocabulary_overrides=VOCABULARY_OVERRIDES,
    starters=STARTERS,
    checks=CHECKS,
    pipeline=PIPELINE,
)


def first_stage_index(pipeline: tuple[StageSpec, ...], kind: str) -> int:
    """Index of the first stage of a given `kind` in a pipeline sequence
    -- used to resolve a *semantic* position (e.g. "the planner",
    "where rework restarts") without hardcoding a role name or position,
    per Rule #16 (Sprint 9)."""
    for index, stage in enumerate(pipeline):
        if stage.kind == kind:
            return index
    raise ValueError(f"pipeline has no stage of kind {kind!r}")


def first_stage_role_key(pipeline: tuple[StageSpec, ...], kind: str) -> str:
    return pipeline[first_stage_index(pipeline, kind)].role_key
