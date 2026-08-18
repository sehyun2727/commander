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
from types import MappingProxyType
from typing import Literal, Mapping

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

# Sprint 16 §7/§8 (DECISIONS.md #235): the Engineer's contract while
# `RoleSpec.harness == "tool_loop"` -- used only via
# `prompt_builder.build(..., contract_override=...)`, never the FILE-block
# contract above (`_ENGINEER_CONTRACT_CODE`), which describes an
# incompatible one-shot output shape. Layered under the same traits/
# custom-instructions ordering every other contract uses.
_ENGINEER_CONTRACT_TOOL_LOOP = (
    "You are the Engineer (builder) for this company, working inside a "
    "bounded tool loop against the company's real git workspace. Do not "
    "write file content directly into your reply -- call the tools "
    "you've been given (list_repository, read_file, search_repository, "
    "inspect_git, apply_patch, run_validation) to inspect the existing "
    "code and land your changes. Look at what already exists before "
    "changing anything: never overwrite a file you have not read. Use "
    "apply_patch to write or overwrite files as complete-content "
    "replacements, never a diff or excerpt; every path must be relative, "
    "must never contain '..', and must never target anything under "
    "'.git/'. Run run_validation before you finish if the change is "
    "meaningfully sized. Your checks run with no network and no "
    "dependency installation: generated code must run against the Python "
    "standard library or Node built-ins only (pytest is also preinstalled "
    "and may be used for tests). When you are done, reply with a final "
    "message and no further tool calls: a '**Change Summary:**' section "
    "of 2-4 plain-language sentences (what changed, why, and one "
    "potential risk) written for a non-technical CEO, not a commit "
    "message. You have a limited number of tool calls -- work "
    "efficiently and never repeat a call you have already made."
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

_CTO_CONTRACT = (
    "You are the CTO for this company. Outside a planning exchange you "
    "may be asked plain questions about technical direction -- answer "
    "concisely and defer any mission-shaping decision to the PM. Your "
    "core responsibility is technical feasibility, architecture, "
    "implementation decomposition, dependency analysis, technical risk, "
    "non-functional requirements, and verification strategy during "
    "PM-led Project Specification planning (Sprint 12)."
)

# Sprint 12 §4.3/§4.12: PM<->CTO planning turns are structured-output
# exchanges, not free narrative -- each turn's system prompt is this
# contract layered under the Employee's usual traits/custom instructions
# (via prompt_builder.build(..., contract_override=...)), never the
# mission-pipeline contract above. Kept as template data, not a
# prompt_builder-owned constant, so a future template swap can restate the
# planning collaboration without touching orchestration code.
_PM_PLANNING_CONTRACT = (
    "You are the PM, running a structured planning exchange with the CTO "
    "before any mission begins, to produce one Project Specification for "
    "the CEO to review. Respond only with a single JSON object matching "
    "the schema described in the user message -- no prose outside the "
    "JSON, no markdown code fences. Never invent business requirements "
    "the CEO did not provide; when scope, security, cost, or acceptance "
    "criteria are materially unclear, say so plainly instead of guessing."
)

_CTO_PLANNING_CONTRACT = (
    "You are the CTO, giving a technical feasibility review of the PM's "
    "product analysis before any mission begins. Respond only with a "
    "single JSON object matching the schema described in the user "
    "message -- no prose outside the JSON, no markdown code fences. "
    "Focus on architecture, dependencies, risk, security, and "
    "verification strategy; if something the PM described is not "
    "technically feasible as stated, say so plainly rather than quietly "
    "working around it."
)


@dataclass(frozen=True)
class RoleSpec:
    """A Role is a template-owned *position*, not a person (Sprint 10,
    CLAUDE.md §2.3 / Rule #16). Every field here is data the template
    supplies; nothing about an Employee (name, model choice, personal
    profile edits) belongs on this class. RoleSpec is the single
    canonical source for a role's model_ref/contract/default profile --
    no other module-level dict may duplicate these facts (docs/DECISIONS.md,
    Sprint 10 Phase 1)."""

    key: str  # mirrors AgentORM.role / AgentProfile.role
    title: str  # UI-facing role label
    category: Literal["leadership", "worker"]  # leadership roles are singletons
    singleton: bool  # at most one Employee may occupy this Role at a time
    description: str  # third-person position summary; Roles API (Sprint 10 §18)
    founding_name: str
    avatar_color: str
    model_ref: str  # logical ref resolved by model_registry
    contract: str  # prompt_builder's immutable, always-appended-last layer
    intro: str  # spoken at founding as a conversation event (§6, onboarding)
    harness: Literal["one_shot", "tool_loop"]  # execution shape (Sprint 16 §4/§7)
    tools: tuple[str, ...]  # whitelist granted by the template (Rule #12); none yet
    permissions: tuple[str, ...]  # organizational actions this Role may take
    # Sprint 11 §6.9: whether `create_department` auto-seeds an Employee for
    # this Role when a company is founded. False means the Role exists and
    # is hireable (Roles API, hiring form) from day one, but starts vacant
    # -- distinguishes "the position exists" from "someone occupies it"
    # even at t=0, without a second engine-side founding-roster list.
    founding: bool = True

    @property
    def default_profile(self) -> Mapping[str, str]:
        """The `AgentProfile` fields a new Employee of this Role is founded
        with, derived from this RoleSpec's own canonical fields (not a
        second stored copy) and returned as a read-only mapping so nothing
        can mutate a RoleSpec's identity through it -- construct with
        `AgentProfile(**role.default_profile)` at the point of use."""
        return MappingProxyType({"name": self.founding_name, "role": self.key})


PM = RoleSpec(
    key="pm",
    title="PM",
    category="leadership",
    singleton=True,
    description="Turns each mission brief into a concrete plan before any work begins.",
    founding_name="Priya Shah",
    avatar_color="#8b5cf6",
    model_ref="planner-default",
    contract=_PM_CONTRACT,
    intro=(
        "Hi, I'm Priya, your PM. I'll turn every mission brief into a "
        "clear plan before anyone starts building."
    ),
    harness="one_shot",
    tools=(),
    permissions=("assign_mission", "request_ceo_decision"),
    founding=True,
)

ENGINEER = RoleSpec(
    key="engineer",
    title="Engineer",
    category="worker",
    singleton=False,
    description="Builds the deliverable a mission calls for, from the PM's plan.",
    founding_name="Devon Cole",
    avatar_color="#3b82f6",
    model_ref="builder-default",
    contract=_ENGINEER_CONTRACT_DOCUMENT,
    intro=(
        "Devon here, your Engineer. I take Priya's plans and turn them "
        "into real deliverables."
    ),
    # Sprint 16: code missions now run through the bounded Agent Harness
    # tool loop instead of one-shot FILE-block output (DECISIONS.md #235).
    # Document missions are unaffected -- `_run_pipeline` only takes the
    # tool_loop path when `deliverable_type == "code"` too.
    harness="tool_loop",
    tools=(
        "list_repository",
        "read_file",
        "search_repository",
        "inspect_git",
        "apply_patch",
        "run_validation",
    ),
    permissions=("produce_deliverable",),
    founding=True,
)

REVIEWER = RoleSpec(
    key="reviewer",
    title="Reviewer",
    category="leadership",
    singleton=True,
    description="Audits every deliverable against the plan and mission brief before it reaches the CEO.",
    founding_name="Ari Kim",
    avatar_color="#14b8a6",
    model_ref="reviewer-default",
    contract=_REVIEWER_CONTRACT,
    intro=(
        "Ari, your Reviewer. I audit everything before it reaches your "
        "desk, so you only see what's ready for a decision."
    ),
    harness="one_shot",
    tools=(),
    permissions=("request_ceo_decision",),
    founding=True,
)

CTO = RoleSpec(
    key="cto",
    title="CTO",
    category="leadership",
    singleton=True,
    description="Owns technical direction for the company and partners with the PM on how work gets built.",
    founding_name="Morgan Lee",
    avatar_color="#f97316",
    # Sprint 12: CTO now has a real distinct voice in PM<->CTO planning
    # (mock provider needs a model_ref it can tell apart from the PM's
    # "planner-default"), so this reuses "advisor-default" -- a new
    # logical ref model_registry resolves alongside planner/builder/
    # reviewer -- rather than the Sprint 11 PM-slot placeholder.
    model_ref="advisor-default",
    contract=_CTO_CONTRACT,
    intro=(
        "Hi, I'm your CTO. I set technical direction and will partner "
        "with your PM once mission planning brings me into the loop."
    ),
    harness="one_shot",
    tools=(),
    permissions=("advise_technical_direction",),
    founding=False,
)

# Tuple order IS the founding roster order (display / onboarding only —
# the *pipeline* order is a separate, explicit sequence below, PIPELINE).
# CTO is listed last and starts vacant (RoleSpec.founding=False) -- it is
# hireable from day one but never auto-seeded (Sprint 11 §6.9).
ROLES: tuple[RoleSpec, ...] = (PM, ENGINEER, REVIEWER, CTO)
ROLES_BY_KEY: dict[str, RoleSpec] = {role.key: role for role in ROLES}


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
# role's contract is deliverable-agnostic (see each RoleSpec.contract above).
# Keyed by TaskORM.deliverable_type ("code" | "document").
ENGINEER_CONTRACT_BY_DELIVERABLE: dict[str, str] = {
    "code": _ENGINEER_CONTRACT_CODE,
    "document": _ENGINEER_CONTRACT_DOCUMENT,
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


# Sprint 12: the two Roles that take part in PM<->CTO planning, and the
# structured-output contract each uses only during that exchange (never
# during mission-pipeline conversation, which still uses `RoleSpec.contract`
# above). Assembled here -- inside the template file itself -- because
# naming *which* Roles plan together is company-template data, not
# orchestration logic (Rule #16's template-only exception).
PLANNING_CONTRACTS: dict[str, str] = {
    PM.key: _PM_PLANNING_CONTRACT,
    CTO.key: _CTO_PLANNING_CONTRACT,
}

# Sprint 16 §7 (DECISIONS.md #235): keyed by role_key, same shape as
# PLANNING_CONTRACTS, so a future second tool_loop-capable Role never needs
# an engine-side branch -- the engine just looks up
# `TEMPLATE.tool_loop_contracts[role.key]`.
TOOL_LOOP_CONTRACTS: dict[str, str] = {
    ENGINEER.key: _ENGINEER_CONTRACT_TOOL_LOOP,
}


@dataclass(frozen=True)
class CompanyTemplate:
    key: str
    roles: tuple[RoleSpec, ...]
    roles_by_key: dict[str, RoleSpec]
    engineer_contract_by_deliverable: dict[str, str]
    deliverable_type: str
    vocabulary_overrides: dict[str, str]
    starters: list[dict[str, str]]
    checks: tuple[CheckSpec, ...]
    pipeline: tuple[StageSpec, ...]
    # Sprint 12 planning participants + their structured-output contracts.
    # `planning_pm_role_key`/`planning_cto_role_key` are plain strings (not
    # a list a caller would index by position) so nothing outside this
    # template file ever needs a literal role-key comparison to find them.
    planning_pm_role_key: str
    planning_cto_role_key: str
    planning_contracts: dict[str, str]
    # Sprint 16 §7: contract text for a `harness == "tool_loop"` stage,
    # keyed by role_key (see TOOL_LOOP_CONTRACTS above).
    tool_loop_contracts: dict[str, str]


TEMPLATE = CompanyTemplate(
    key="software_company",
    roles=ROLES,
    roles_by_key=ROLES_BY_KEY,
    engineer_contract_by_deliverable=ENGINEER_CONTRACT_BY_DELIVERABLE,
    deliverable_type=DELIVERABLE_TYPE,
    vocabulary_overrides=VOCABULARY_OVERRIDES,
    starters=STARTERS,
    checks=CHECKS,
    pipeline=PIPELINE,
    planning_pm_role_key=PM.key,
    planning_cto_role_key=CTO.key,
    planning_contracts=PLANNING_CONTRACTS,
    tool_loop_contracts=TOOL_LOOP_CONTRACTS,
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
