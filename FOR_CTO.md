# Commander — CTO Handover

> Written for the next senior engineering AI joining Commander cold.
> This is a private engineering notebook, not a README. Read it once, then read the code.
>
> **Trust rule:** documentation explains intent, source explains reality. When the two disagree, believe the code — but flag the drift.

---

## 1. Executive Understanding

**Commander is not a program that gives work to AI. Commander is an operating system for running an AI company.**

A solo operator becomes the **CEO of an AI software company.** AI Employees do the work; the CEO governs the organization — sets direction, reads reports, and makes CEO Decisions.

The competitive claim is not "a better coding agent." It is the **organization layer** sitting above replaceable AI workers: PM ↔ CTO plan; CTO delegates to Employees; Reviewer audits; PM judges (Minor/Major/Critical); only Critical decisions reach the CEO.

- **Repository language vs product language.** The code uses engineering terms (`ProjectORM`, `TaskORM`, `AgentORM`); the UI must say `Company`, `Mission`, `Employee`. See CLAUDE.md §3.
- **Backend:** FastAPI (Python 3.11+), async SQLAlchemy, Alembic, Postgres in prod, SQLite in tests, single async worker.
- **Frontend:** Next.js App Router + TypeScript + Tailwind + TanStack Query, one SSE stream per Company.
- **Providers:** Mock (default, zero keys) and Anthropic (real). Provider identity is never hardcoded above `ProviderGateway`.
- **Status:** V1 shipped as `v1.0.0` (Sprint 8). V1.1 in development. **Sprint 18 (Project Memory) is complete** — see §18b for the addendum; §1/§2 below are otherwise the Sprint-16-era snapshot, still accurate except where §18a/§18b/§7.14/§12.13/§12.14/§13/§19 override it.

Test baseline right now: **512 passed, 6 skipped** (2 of the skips are Windows symlink-privilege skips in `test_agent_harness_guards.py`, honestly recorded — not silently passed; Sprint 17 added 17 new/changed tests on top of Sprint 16's 455, Sprint 18 added 40 more on top of Sprint 17's 472).

---

## 2. Current State

- **Branch:** `master`, clean working tree, local HEAD == origin/master (as of Sprint 18 close-out).
- **Alembic head:** `c2a7e1f4b6d3` (adds `memory_records`, `down_revision = 'b1f4c8d5e9a2'`; one linear chain, no branching).
- **PROGRESS.txt** is the live checkpoint file — read it directly for the current line-item state rather than trusting a snapshot here.

### What is genuinely built

- V1 core (Sprints 1–8): Company/Mission CRUD, PM→Engineer→Reviewer pipeline, git-backed workspace per Company, Docker sandbox for template `CheckSpec` commands, approvals, mock + Anthropic providers with three-tier model resolution, Reports, Payroll/costs, Timeline/SSE.
- Sprint 9: local email+password auth (session cookies, SHA-256 token hash at rest), orphan-mission recovery, cooperative `asyncio` cancellation, per-Mission budget guard.
- Sprint 10: **Role/Employee split.** `RoleSpec` = template-owned data; `AgentORM.role_key` = CEO-owned instance. Idle-first resolver, AST guard against Rule #16 violations.
- Sprint 11: CTO role (singleton, `founding=False`, vacant at creation), hiring flow (`POST /api/projects/{id}/agents`), DB-backed `role_singleton_locks` for race-safe singleton hiring, skill-template registry.
- Sprint 12: **PM↔CTO planning + Project Specification** lifecycle (`app/modules/planning/`), `Specification` aggregate with 9-state machine, DB-backed `active_specification_locks`, versioned `SpecificationVersion`, CEO approval gate before Mission creation.
- Sprint 13: `workspace_overview` read-only projection + pure-function `next_action` precedence policy.
- Sprint 14: CEO Workspace UI shell at `/company/[id]`.
- Sprint 15: `workspace_widgets` registry (8 widgets, 2 required), per-`(user_id, project_id)` preferences with integer-`revision` optimistic concurrency.
- **Sprint 16: Secure Agent Harness.** `app/modules/agent_harness/` — bounded tool loop for `RoleSpec.harness == "tool_loop"` Roles on `deliverable_type == "code"` Missions. Full detail in §7 below.
- **Sprint 17: Self-correction.** Termination-interception correction loop + server-computed rollback tool. See §18a.
- **Sprint 18: Project Memory.** `app/modules/memory/` — deterministic event-derived projection into `memory_records`, PM-explicit-only recall wired into `PlanningOrchestrator`, idempotent backfill for pre-subscriber history. No new HTTP route, no dashboard surface. See §18b.

### What is NOT built

- Sprint 19 Mission Tree + remaining widgets.
- Sprint 20 V1.1 release.
- Decision-authority Minor/Major/Critical classification — **not in code** (Sprint 13 built the CEO Workspace projection instead).
- Second company template. There is only `software_company`; no template picker exists (UX_SPEC §10.2 "hidden means absent").
- Any Backend/Frontend Engineer split — the only Engineer is the generic `ENGINEER` RoleSpec.
- Any Role beyond PM / CTO / Engineer / Reviewer.
- Any Employee-firing flow. Once hired, singletons stay put; `role_singleton_locks` rows are never deleted (§6.5 accepted tradeoff).
- Docker sandbox `--read-only` (deliberate — checks legitimately write `__pycache__`/coverage files under `/workspace`).

---

## 3. System Architecture

### 3.1 Modules (backend, `apps/api/app/`)

```
core/
  events/          Event envelope + registered types + build_event()
  interfaces/      Ports: agent_runtime, event_bus, provider_gateway,
                   sandbox, workflow_engine, workspace_manager
  lifecycle/       agent_states, task_states, specification_states,
                   state_machine (transition validator)
  db.py            AsyncEngine + async_session_factory
  db_models.py     Every ORM table (shared infra, imported freely)
  secrets.py       SecretsProvider port + DBSecretsProvider (env fallback)
  ownership.py     project_owned_by / resource_owned_by (Rule #15)
  config.py        settings singleton (pydantic-settings)
  boot_checks.py   Fail-fast startup validation
  errors.py        Named CommanderError subclasses
  contracts.py     AgentProfile (Pydantic)

templates/
  software_company.py   The ONE company template. Owns RoleSpec/StageSpec/
                        CheckSpec/PLANNING_CONTRACTS/TOOL_LOOP_CONTRACTS.
                        See §5 and §6.

modules/
  agent_harness/      Sprint 16 — see §7
  agent_profiles/     CEO-editable Employee profile (JSON on AgentORM.profile)
  agent_runtime/      DBAgentRuntime — Employee CRUD + state transitions
  approvals/          CEO Decisions (approve/request_changes/reject)
  auth/               Local email+password + session cookie
  costs/              Per-call token → USD accounting, usage_for_task()
  event_bus/          InProcessEventBus — persist→fan-out→SSE
  model_registry/     Logical refs (planner-default → provider/model)
  planning/           Sprint 12 PM↔CTO orchestrator + specification service
  projects/           Company CRUD + founding department
  prompt_builder/     Pure profile+role → system prompt
  provider_gateway/   MockProvider + AnthropicProvider + RoutedProviderGateway
  realtime/           SSE stream per project
  reports/            Daily Reports
  sandbox/            DockerSandbox + FakeSandbox + detect_checks
  situation/          One-line PM-voiced status
  skill_templates/    Frozen SkillTemplate registry (3 entries)
  tasks/              Mission CRUD + Meetings + orphan recovery
  timeline/           Cursor-paginated events + kind filter
  workflow_engine/    THE brain — CommanderWorkflowEngine + parsing +
                      employee_resolution
  workspace_manager/  LocalGitWorkspaceManager (one real git repo per Company)
  workspace_overview/ Sprint 13 read-only snapshot + next_action policy
  workspace_widgets/  Sprint 15 widget registry + per-CEO preferences
```

### 3.2 Dependency direction (enforced, Rule #1/#5)

```
Events (core.events)  →  Domain Modules  →  Workflow (engine)  →  API (routes)
```

Modules never import each other's internals. Cross-module communication is EventBus (`core.interfaces.event_bus`) or a public function of the target module (`from ..tasks import create_task`). Shared infra (`core.db_models`, `core.events`, `core.secrets`, `core.ownership`) may be imported directly — Rule #1 is about module-to-module coupling, not the shared floor. `agent_harness/audit.py` and `tasks/service.get_harness_summary` both read `HarnessToolCallORM` this way; that is **not** a Rule #1 violation.

### 3.3 High-level runtime picture

```
Browser
  ├─ REST (credentials: include, HttpOnly session cookie)
  └─ SSE /api/events/stream?project_id=...  (heartbeat 15s, dedup by event.id)
      │
      ▼
FastAPI (single asyncio worker, in-process EventBus, no broker)
  auth guard on every non-health/non-auth route
  ownership.project_owned_by → 404 (never 403, Rule #15)
      │
      ▼
Domain services (project/task/planning/etc.) — plain async functions
      │
      ▼
CommanderWorkflowEngine — background asyncio.Task per Mission
      │
      ├──── one_shot Role ─────► _run_role → streamed CompletionResult
      └──── tool_loop Role ────► _run_engineer_tool_loop → run_tool_loop
                                    └── dispatch_tool_call (schema→auth→run→bound→audit)
                                          └── WorkspaceManager / SandboxRunner
```

### 3.4 Wiring point

`apps/api/app/main.py::lifespan` is the ONE place singletons are built and stapled to `app.state.*`. FastAPI routes read them via `apps/api/app/deps.py`. Tests (`apps/api/tests/conftest.py`) override those `Depends` with an isolated `Harness` — sqlite temp file, `LocalGitWorkspaceManager` in tmp dir, `FakeSandbox`. If you need a service anywhere else, go through `deps.py`; do not construct singletons inline.

---

## 4. End-to-End Execution Flow

### 4.1 Founding a Company

1. `POST /api/projects` → `projects.service.create_project` → `ProjectORM` insert + `PROJECT_CREATED` event.
2. `agent_runtime.create_department(project_id)` seeds founding Employees for every `RoleSpec.founding == True` role (PM, Engineer, Reviewer). CTO is `founding=False` — vacant at creation.
3. `RoleSingletonLockORM` rows are inserted in the same transaction as the founding singleton Employees (DECISIONS.md #183 — otherwise the first post-founding hire for a founding singleton would slip through).

### 4.2 Planning (Sprint 12)

1. `POST /api/projects/{id}/specifications` with `request_text`.
2. `planning.service.start_planning` builds a `PlanningOrchestrator`, inserts a `SpecificationORM` row (status `draft`) **and** an `ActiveSpecificationLockORM` row in the same transaction — race-safe rejection of concurrent planning starts (`IntegrityError → ActivePlanningExistsError → HTTP 409`).
3. `PlanningOrchestrator._run` walks a bounded turn loop (`MAX_PLANNING_TURNS = 6`, `MAX_MALFORMED_ATTEMPTS = 2`) driven by the `_role_for_kind` dispatch on `turn kind` strings (`"pm_analysis"`, `"cto_review"`, `"pm_draft_or_followup"`, ...). Rule #16 is preserved by branching on turn kinds (workflow-stage semantics), never on a hardcoded role key literal.
4. Each turn is a `gateway.complete(...)` call using a JSON-only planning contract (`TEMPLATE.planning_contracts[role_key]`) layered under the Employee's usual traits via `prompt_builder.build(..., contract_override=...)`. Response text is parsed by `_parse_json` + `_VALIDATORS[kind]`; malformed retried up to `MAX_MALFORMED_ATTEMPTS`, then `MalformedProviderOutputError` → spec `failed`.
5. Result: a versioned `SpecificationVersionORM` (immutable per version — "revision" appends a new row and bumps `SpecificationORM.current_version`), spec status transitions to `ready_for_review`.
6. `POST /specifications/{id}/begin-execution` (`begin_execution`) is the **only** path from an approved spec to a Mission — validates approval + "one Mission per Specification" + delegates to `tasks.service.create_task`/`assign_task`. Pre-Sprint-12 Missions remain valid with `specification_id = NULL`.

### 4.3 Mission execution (workflow_engine)

`CommanderWorkflowEngine._run_pipeline(task_id, resume_from, ceo_comment)` iterates `TEMPLATE.pipeline` (a `tuple[StageSpec, ...]`) starting at `resume_from` — **by index, not role_key**, since the same `kind` can repeat. The engine dispatches on `stage.kind` (a workflow-stage label, Rule #16-permitted), never on the role name.

For each stage:

1. Resolve the Employee via `employee_resolution.resolve_employee_for_role(agents[role_key])` — idle-first, then longest-since-`last_assigned_at`, tie-break on `created_at`/`id`. Emits `AGENT_RESOLVED`.
2. `_check_budget(task, stage.role_key)` — checked **before every stage** against `commander_mission_max_tokens/_usd/_seconds`. Exceeding any cap raises `BudgetExceededError`; the top-level handler transitions the Mission to `BLOCKED` and publishes `BUDGET_EXCEEDED` + `TASK_STATE_CHANGED`.
3. Dispatch by `stage.kind`:
   - **`plan`:** publishes `TASK_STARTED`; runs `_run_role` (streamed reply, `_stream_say` publishes `CONVERSATION_MESSAGE_DELTA` transiently and one persisted `CONVERSATION_MESSAGE` at end).
   - **`produce`:** publishes `CODING_STARTED`; branches on `role_spec.harness == "tool_loop" and task.deliverable_type == "code"`:
     - **tool_loop path (Sprint 16):** `_run_engineer_tool_loop` → creates workspace + branch **before** the loop (unlike one-shot which lands after), builds `ToolRunContext` from server-trusted data, `resolve_permitted_tools`, calls `run_tool_loop`, then `_land_tool_loop_changes` (uses `diff_stats()` — `apply_patch` may commit multiple times per attempt, so a single `CommitResult` no longer represents the whole attempt).
     - **one-shot path:** `_run_role` (produces one FILE-blocked deliverable text), then `_land_code_changes` (parses FILE blocks with `parsing.parse_file_blocks`, `write_files` + `commit`).
     - After landing, if `stage.runs_checks`, `_run_checks` runs matched `TEMPLATE.checks` via `SandboxRunner.run_check`. Results feed into the Reviewer's context; they are Reviewer evidence, **not a hard gate** (deliberate V1 design, unchanged by Sprint 16).
   - **`review`:** publishes `REVIEW_STARTED`; runs `_run_role`; `parsing.parse_verdict` reads the trailing `**Verdict:**` line (this is the **one hard contract** in the pipeline — Reviewer output is provider-agnostic); persists an `ApprovalORM` row (status `pending`) with parsed sections + raw summary; publishes `REVIEW_COMPLETED` + `TASK_STATE_CHANGED(→ PENDING_APPROVAL)` + `APPROVAL_REQUESTED`.

### 4.4 CEO Decision (approvals)

`POST /api/approvals/{id}/decide` → `approvals.service.decide` → `WorkflowEngine.resume_after_decision(task_id, decision, comment)`:
- `approve` → `_approve_task`: for code Missions with a branch, `WorkspaceManager.merge`; conflict → `_block_task_on_merge_failure` (Mission `BLOCKED`, no auto-resolve). Then `_finish_task(COMPLETED, ...)` publishes `APPROVAL_GRANTED` + `TASK_COMPLETED` (and `BRANCH_MERGED` if merged).
- `reject` → `_finish_task(CANCELLED, ...)` publishes `APPROVAL_REJECTED` + `TASK_CANCELLED`. Branch is preserved.
- `request_changes` → bumps `attempt`, transitions back to `IN_PROGRESS`, marks approval `changes_requested`, publishes `APPROVAL_CHANGES_REQUESTED` + `TASK_RETRIED`, and re-spawns `_run_pipeline` starting at `_REWORK_STAGE_INDEX = first_stage_index(TEMPLATE.pipeline, "produce")` — semantic position, not a hardcoded role name.

### 4.5 Cancellation

Cooperative asyncio only. `POST /api/tasks/{id}/cancel` → `WorkflowEngine.cancel_task(task_id, reason)`:
- Stores the reason in `self._cancel_reasons` (payload for the upcoming `CancelledError`).
- `self._running[task_id].cancel()` — the pipeline coroutine sees `CancelledError` at its next `await`.
- The pipeline's `except asyncio.CancelledError` block: `_finish_task(CANCELLED, ...)` and re-raises.
- `_release_agent_to_idle` walks the Employee back to `IDLE` via the state machine's legal edges and clears `current_task_id`. `AgentState` has no direct WORKING→IDLE edge, so this uses (state)→FAILED→IDLE or WAITING_REVIEW→COMPLETED→IDLE.
- `asyncio.CancelledError` inherits from `BaseException` (not `Exception`), so nothing in `run_tool_loop`'s `except (ToolDeniedError,...)`/`except _RETRIABLE_TOOL_ERRORS` clauses ever catches it — it propagates cleanly.

### 4.6 Orphan recovery on restart

`main.py::lifespan` runs `tasks.recover_orphaned_tasks(session_factory, event_bus)` **before** serving traffic. Any `TaskORM` still in `IN_PROGRESS`/`IN_REVIEW` when the last process died has no coroutine to move it, so it's transitioned to `BLOCKED` with `TASK_RECOVERED`; any Employee with `current_task_id` in the recovered set is walked back to `IDLE` via `_AGENT_RECOVERY_STEPS`. Missed during Sprint 9 Phase 5 DoD verification (the Employee walk-back was originally forgotten) — DECISIONS.md #162.

---

## 5. Domain Model

### 5.1 Entities (`core/db_models.py`)

| Table | Owned by | Purpose | Notes |
|---|---|---|---|
| `users` | Self | CEO account | `password_hash` may be NULL for non-local providers (schema shape prevents plaintext) |
| `sessions` | User | Auth session | Primary key = SHA-256 of the raw token; the raw token exists only in the browser cookie |
| `projects` | User (`owner_id`) | Company | Provider (`mock`/`anthropic`) chosen per project |
| `agents` | Project | Employee | `role_key` → `RoleSpec`; `profile` is `AgentProfile.model_dump(mode="json")`; `last_assigned_at` powers idle-first resolver |
| `role_singleton_locks` | Project | Composite PK `(project_id, role_key)`; DB-enforced singleton | Never deleted (no firing flow yet) |
| `tasks` | Project | Mission | `deliverable_type` = `"code"`/`"document"`; `branch_name`, `code_stats` JSON, `check_results` JSON; `specification_id` FK (nullable) forms a cycle with `SpecificationORM.source_task_id` — resolved via `use_alter=True` |
| `events` | Project | The single event stream (Rule #8) | Autoincrement `seq` is authoritative order; `id` is UUID for dedup |
| `approvals` | Task | Pending CEO Decision | Reviewer id/name captured at write time (no join to render); lenient `sections` JSON + `raw_summary` |
| `cost_entries` | Task | Per-call token→USD | Derived telemetry, not Timeline |
| `reports` | Project | On-demand Daily Report snapshot | |
| `settings_kv` | Global | Runtime KV (provider override, secrets) | |
| `specifications` | Project | Aggregate for a planning run + spec doc | `status` FSM in `specification_states.py`; `current_version` points into `specification_versions` |
| `specification_versions` | Specification | Immutable versioned draft | Revision appends a new row; `title`/`problem_statement`/`goals`/`requirements`/`acceptance_criteria`/`architecture_components`/`risks`+mitigations/`dependencies`/`assumptions`/`unresolved_questions`/`implementation_stages`/`technical_approach`/`data_migration_impact`/`security_considerations`/`observability_requirements`/`test_plan` |
| `specification_turns` | Specification | One PM/CTO/CEO turn | Authoritative for "planning activity"; parallel to `SpecificationTurnPosted` events |
| `active_specification_locks` | Project | PK `(project_id)`; one non-terminal spec per Company | DB-race-safe |
| `workspace_preferences` | (user_id, project_id) | Widget layout | One JSON row + integer `revision` for optimistic concurrency (`StaleRevisionError → 409`) |
| `harness_tool_calls` | Task/Agent | Sprint 16 durable per-call audit | `arguments_summary` is content-free (bounded); `output_excerpt` is bounded via `output.bound_output`; **never** raw file bodies |
| `memory_records` | Project | Sprint 18 event-derived Company Knowledge row | `UNIQUE(source_event_id)` is the sole dedup guarantee (shared by the live subscriber and `backfill_memory`); `category` is one of the frozen six in `memory/registry.py`; bounded `content_json`/`tags`/`keywords_text` |

### 5.2 State machines (`core/lifecycle/`)

- **AgentState:** `IDLE → ASSIGNED → PLANNING → WORKING → WAITING_REVIEW → COMPLETED → IDLE` (with `BLOCKED`/`FAILED` off-ramps). `_release_agent_to_idle` in the engine walks the multi-hop path any interrupted state requires.
- **TaskState:** `CREATED → ASSIGNED → IN_PROGRESS → IN_REVIEW → PENDING_APPROVAL → COMPLETED`, plus `FAILED`/`RETRYING`/`CANCELLED`/`BLOCKED`. Rework: `PENDING_APPROVAL → IN_PROGRESS` (attempt+1).
- **SpecificationStatus:** 9 states (`draft → planning → {clarification_required, ready_for_review} → {approved, revision_requested, rejected, cancelled, failed}`). `TERMINAL_SPECIFICATION_STATUSES` is `{approved, rejected, cancelled, failed}` — planning lock is released only when a terminal state is reached (or by a CEO decision path).

All transitions go through `state_machine.transition(current, target, TABLE)` — never a bare `.state = ...`. `InvalidTransition` is raised, not swallowed. There is no separate `on_transition` publish; each caller publishes its own state-change event with the right actor and reason.

### 5.3 The CEO/PM/CTO/Engineer/Reviewer distinction (Rule #16)

- `RoleSpec` (`app/templates/software_company.py`) is **template-owned data**: `key`, `title`, `category` (leadership/worker), `singleton`, `founding`, `description`, `founding_name`, `avatar_color`, `model_ref`, `contract`, `intro`, `harness` (`"one_shot"` | `"tool_loop"`), `tools` (whitelist, Rule #12), `permissions`.
- `AgentORM` is a **CEO-owned instance** with `role_key`, `name`, `profile`, `avatar_color`, `state`, `current_task_id`, `last_assigned_at`.
- The engine, prompt builder, and workflow modules may **only** branch on `RoleSpec` fields (`role_spec.harness`, `role_spec.tools`) or `StageSpec.kind`. Branching on `role == "engineer"` is forbidden. The AST guard `tests/test_role_hardcoding_guard.py` scans all of `app/` except `app/templates/` and derives its role-key list from the live template — new roles/modules are automatically covered.

---

## 6. Planning / PM / CTO Architecture

### 6.1 What's built (Sprint 12)

- `app/modules/planning/` — `orchestrator.py`, `service.py`, `routes.py`, `schemas.py`.
- `PlanningOrchestrator` is built **fresh per call** (mirrors `build_gateway()`, unlike `CommanderWorkflowEngine` which is a lifespan singleton). Rationale: every planning turn burst runs to completion inside one awaited call; nothing keeps running between calls (PROGRESS.txt Phase 0 design decision 0.8).
- Budgets (Rule #13):
  - `MAX_PLANNING_TURNS = 6` — lifetime per Specification, cumulative across revisions.
  - `MAX_MALFORMED_ATTEMPTS = 2` — bounded retry per turn.
- Concurrency: `ActiveSpecificationLockORM(project_id)` PK, DB-enforced. Racing starts → 409.
- Structured output: PM/CTO turns respond with JSON only, validated by `_VALIDATORS[kind]` in `orchestrator.py`. `_parse_json` tolerates markdown code fences.
- Contracts: `TEMPLATE.planning_contracts[role_key]` supplies the JSON-only contract; the mission-pipeline contract (`RoleSpec.contract`) is never used during planning.
- Approval gate: `POST /specifications/{id}/begin-execution` (`planning.service.begin_execution`) is the ONLY path from an approved spec into a Mission. Validates status + one-Mission-per-Specification, then calls `tasks.service.create_task`/`assign_task`.

### 6.2 CEO-facing surface (Rule #11 / #17)

The CEO's **only** conversational counterpart is the PM. There is no CEO route to the CTO or Engineer. The Specification lifecycle is a Sidebar page (`/company/[id]/specifications`), never bolted onto the PM conversation. The transcript is the CEO's window into the PM↔CTO discussion.

### 6.3 What is NOT built in planning

- No "Minor/Major/Critical" decision classifier in code.
- No CEO-initiated cancellation of an in-flight planning turn burst mid-turn (only after each turn completes; the whole burst runs to completion inside one awaited call).
- No planning-phase model overrides beyond the standard three-tier resolution (`agent.profile.model_ref` > CEO per-role override > registry default).

---

## 7. Agent Runtime Architecture (the important one — Sprint 16)

**Read `apps/api/app/modules/agent_harness/` before touching anything in this section.**

### 7.1 Why it exists

Before Sprint 16, `ENGINEER.harness = "one_shot"` produced one long response with `===== FILE: path =====` blocks parsed by `parsing.parse_file_blocks`. The Engineer could not inspect the existing repo, could not iterate, could not validate before shipping. Sprint 16 makes `ENGINEER.harness = "tool_loop"` on code Missions the default: a bounded provider/tool loop with six tools.

Sprint 16 **also** deliberately does not implement:
- Any self-correction across runs (Sprint 17).
- Any organizational memory (Sprint 18).
- Any Role beyond Engineer using `tool_loop`.
- Any generic shell / arbitrary command / arbitrary executable tool (Rule #9/#12 — permanent).

### 7.2 The tool registry (`agent_harness/registry.py`)

Immutable, code-owned, seven tools (`revert_last_patch` added Sprint 17):

| Key | Mutates | Purpose | Backing |
|---|---|---|---|
| `list_repository` | No | List files under path in mission branch | `WorkspaceManager.list_tree` |
| `read_file` | No | Read one file at branch ref | `WorkspaceManager.read_file` (resolves through committed ref, not working tree) |
| `search_repository` | No | Substring search in files | Iterates `list_tree` + `read_file` |
| `inspect_git` | No | Unified diff branch vs main | `WorkspaceManager.diff` |
| `apply_patch` | **Yes** | Full-file-content replacements (not diff hunks) | `WorkspaceManager.write_files` + `commit` |
| `run_validation` | No | Run a named `CheckSpec` in the sandbox | `SandboxRunner.run_check` |
| `revert_last_patch` | **Yes** | Undo the loop's own last `apply_patch` commit | `WorkspaceManager.revert_last_commit` (Sprint 17) |

All seven require capability `"repository_tools"` (present on all three `SkillTemplate`s). No `run_shell`, no `install_package`, no `network_fetch`, no `delete`, no arbitrary git remote — **and these are not just missing, they're intentionally never in `TOOLS_BY_KEY`.** Rule #9 (permanent). `revert_last_patch` takes **zero provider-supplied arguments** (`RevertLastPatchArgs` has no fields, `extra="forbid"`) — the rollback target is always server-computed (§7.14), never provider input.

### 7.3 Permission intersection (`agent_harness/permissions.py`)

**Fail-closed AND across five terms.** Any missing/false term denies:

```
harness_enabled ∩ RoleSpec.tools ∩ SkillTemplate.capabilities ∩ (stage_kind == "produce") ∩ workspace_ready
```

- `ELIGIBLE_STAGE_KINDS = frozenset({"produce"})` — tools are unavailable during `plan`/`review` stages, preserving the planning-stage non-mutation guarantee.
- `authorize_tool_call` is called immediately before **every** tool handler invocation (not once per loop) — `stage_kind`/`workspace_ready` can change between calls within the same loop.
- A provider cannot self-grant a tool by naming one in output — `tool_name not in TOOLS_BY_KEY` → `ToolDeniedError("unknown tool")`.

### 7.4 Path/content guards (`agent_harness/guards.py`)

Reuses `workspace_manager/validation.py`'s `validate_path`/`validate_content` (relative-only, no `..`, no `.git/`, no drive-letter, `.resolve()`+`relative_to()` real confinement) and **adds one narrower check**: rejects any resolved target that is itself a symlink (a "confused deputy" gap `validate_path` was never designed to catch, since it was written for the one-shot Engineer's not-yet-existing writes).

`.resolve()` already follows symlinks in existing path components, so a symlink planted inside the repo pointing outside it is already caught by the confinement check.

### 7.5 Tool-call schemas (`agent_harness/schemas.py`)

Pydantic v2 models with `ConfigDict(extra="forbid")`. Every tool has an argument model in `TOOL_ARGUMENT_SCHEMAS`. Bounds mirror the existing workspace-manager bounds:
- `MAX_PATCH_FILES = 30` (== `MAX_FILES_PER_ATTEMPT`)
- `MAX_FILE_BYTES = 256 * 1024`
- `MAX_PATH_LENGTH = 4096`
- `MAX_SEARCH_PATTERN_LENGTH = 256`

`PatchFileEntry.expected_content` is the optional stale-write guard — if supplied and the file has changed since the Engineer last read it, `apply_patch` raises `PatchConflictError` and the whole patch is rejected.

### 7.6 Budgets (`agent_harness/budget.py`, Rule #13)

`HarnessBudget` is per-attempt, never shared. Two dimensions:
- `max_tool_calls` — default `settings.commander_harness_max_tool_calls = 40`
- `max_seconds` (wall time from budget construction) — default `600`

Exhaustion raises `BudgetExceededError` — the **same** exception the mission-level budget guard uses, so it reaches the same `_block_task_on_budget` path (Mission → BLOCKED with `BUDGET_EXCEEDED` + `TASK_STATE_CHANGED` events). `check()` is called before every provider call and before every tool dispatch.

There is also a **mission-level** budget: `commander_mission_max_tokens = 200_000`, `commander_mission_max_usd = 5.0`, `commander_mission_max_seconds = 900`. Both guards are always in effect; harness exhaustion is one attempt, mission exhaustion is the whole Mission's lifetime.

### 7.7 The orchestrator (`agent_harness/orchestrator.py`)

`run_tool_loop` is the ONE bounded provider/tool loop. Called once per produce stage by `workflow_engine.engine._run_engineer_tool_loop`. It:

1. Builds `tools=[...]` schemas from the immutable registry + pydantic schemas via `tool_schemas_for(permitted_tools)`. Anthropic-shaped `{name, description, input_schema}`. Never cached — per-Employee/stage/company.
2. Loops:
   - `context.budget.check()` before every provider call.
   - `gateway.complete(model_ref, system, messages, tools=tools, agent_override=...)`.
   - If no `tool_calls`, return `ToolLoopResult` with the final text.
   - Otherwise append assistant blocks (`{"type": "tool_use", "id", "name", "input"}`) to `messages`, then for each tool call:
     - `context.budget.check()` again (before each dispatch).
     - **Idempotency:** if `call.call_id in seen_call_ids`, respond with `duplicate call_id; already handled, ignored` — never re-executes. Critical because `apply_patch` is mutating.
     - `context.budget.record_tool_call()`.
     - `dispatch_tool_call(...)` (see §7.8).
     - On `ToolDeniedError`: `denied_streak += 1`, reset `malformed_streak`. Bound `MAX_DENIED_STREAK = 2` → `ToolLoopExhaustedError`.
     - On `ToolCallMalformedError`/`ToolPathViolationError`/`PatchConflictError`: `malformed_streak += 1`, reset `denied_streak`. Bound `MAX_MALFORMED_STREAK = 3` → `ToolLoopExhaustedError`.
     - Success resets both streaks. Response appended as `{"type": "tool_result", "tool_use_id", "content"}` (with `is_error: True` on failures).
3. Never catches `asyncio.CancelledError` — it propagates through the `await` (BaseException, not Exception).

### 7.8 Dispatch (`agent_harness/handlers.py`)

`dispatch_tool_call(context, *, workspace_manager, sandbox_runner, session_factory, tool_name, call_id, raw_arguments)` is the single entry point. Flow:

1. Schema lookup (`TOOL_ARGUMENT_SCHEMAS.get(tool_name)`) — unknown tool → `ToolDeniedError`.
2. `schema.model_validate(raw_arguments)` — `ValidationError → ToolCallMalformedError`.
3. `authorize_tool_call(...)` — `ToolDeniedError` sets `status = "denied"`.
4. Handler runs (all take `ToolRunContext` + validated args + WorkspaceManager/SandboxRunner as needed).
5. Output bounded via `output.bound_output` (default 16 KiB).
6. `finally` block writes exactly one `HarnessToolCallORM` row via `audit.record_tool_call`. Every outcome (success/denied/error) is audited, including malformed and unknown-tool.

`apply_patch` specifics:
- **Pre-validates every file** (`guard_path` + `guard_content`) before writing any (reject-whole-patch-on-any-violation).
- **Commits immediately** after a non-empty `write_files` (DECISIONS.md #234 — the Phase 0 plan of deferring the commit didn't survive because every read tool resolves through a committed ref via `git ls-tree`/`git show`, so an uncommitted patch would be invisible to the Engineer's own next read).
- Byte-identical rewrites cause `write_files` to still report the path as "written" but `commit()` has nothing staged → `ValueError`. This is treated as a benign no-op (DECISIONS.md #236); nothing else in `local_git.py` raises `ValueError`, so the narrow `except ValueError` cannot mask an unrelated failure.
- If `write_files.skipped` is non-empty (race between guard and manager), the whole patch is rejected via `ToolPathViolationError` — never silently lands partial.

`run_validation` specifics:
- Profile resolved from `agent_harness/profiles.py::VALIDATION_PROFILES_BY_NAME` — which is exactly `TEMPLATE.checks` (reuses the existing `CheckSpec` tuple, not a second registry). The provider selects a profile **name** only.
- If `get_execution_enabled(session_factory, project_id)` is False, returns a plain-text "execution disabled" message. Never raises.
- If profile unknown → `ToolDeniedError` (never a default).
- Runs via `SandboxRunner.run_check(profile.name, files, list(profile.command))` — files come from `list_tree` + `read_file`. Sandbox trouble never raises (see §11).

### 7.9 Server-issued run context (`agent_harness/context.py`)

`ToolRunContext` is a frozen dataclass constructed once per loop from **server-trusted data only**: `project_id`, `task_id`, `agent_id`, `repo_root` (from `WorkspaceManager.repo_root`, not from provider), `branch_name`, `branch_base_sha` (Sprint 17 — the mission branch's HEAD at creation, via `WorkspaceManager.head_sha`, seeds `revert_last_patch`'s rollback floor), `role` (`RoleSpec`), `skill_template`, `stage_kind`, `harness_enabled`, `workspace_ready`, `budget`. **Never derived from provider output.**

Note: `agent_id` is the acting Employee's `AgentORM.id`, not `RoleSpec.key`. Caught before hitting a real FK violation (PROGRESS.txt 2.5).

Sprint 17 also adds `LoopState` (`agent_harness/context.py`) — a plain **mutable** dataclass, deliberately separate from the frozen `ToolRunContext`, owned by the orchestrator and threaded through as an optional `loop_state` kwarg into `dispatch_tool_call`/`apply_patch`/`run_validation`/`revert_last_patch`: `last_validation_status` (from `CheckResult.status`, never text-parsed), `correction_attempts`, `first_correction_emitted`, `apply_patch_commit_history: list[str]`. See §7.14.

### 7.10 Persistence & observability (Sprint 16-sanctioned split)

- **Per-call audit:** `HarnessToolCallORM` — durable, engineering evidence. Written in a `finally` block so every outcome is recorded. `arguments_summary` is deliberately content-free (a 30-file `apply_patch` could otherwise duplicate ~7.5MB per row); `output_excerpt` is bounded.
- **Stage-boundary Timeline events:** `CODING_STARTED`, `CODE_CHANGED`, `EXECUTION_*`, `TASK_STATE_CHANGED`, `REVIEW_*`. These stay coarse-grained (CEO-visible narrative). **No per-tool-call Timeline event.**
- **Read-only aggregate:** `GET /api/tasks/{task_id}/harness-summary` (`tasks/service.get_harness_summary`) — counts and tool names only, never `arguments_summary`/`output_excerpt` content. Follows the `GET .../diff` pattern (`resource_owned_by` → 404, service `None` → 404).

**There is no dashboard UI for the summary yet** — it's supplementary evidence, not something the CEO needs to make decisions. `MissionDetail.tsx` still surfaces `code_stats`/`check_results`. A Sprint 17+ widget can add it later.

### 7.11 Reviewer receives real evidence

`_land_tool_loop_changes` uses `WorkspaceManager.diff_stats()` (branch-vs-main aggregate — new in Sprint 16 for #234's deferred consequence) since `apply_patch` may commit multiple times per attempt. The Reviewer then gets `change_summary + diff_text + check_summary` exactly like the one-shot path (`engine.py:886-897`). `run_checks` still runs after the loop as defense-in-depth, even though the Engineer's own `run_validation` may have run inside the loop.

### 7.12 Failure taxonomy

| Exception | Path |
|---|---|
| `ToolDeniedError` | Retried up to `MAX_DENIED_STREAK` (2), then `ToolLoopExhaustedError` |
| `ToolCallMalformedError`/`ToolPathViolationError`/`PatchConflictError` | Retried up to `MAX_MALFORMED_STREAK` (3), then `ToolLoopExhaustedError` |
| `ToolLoopExhaustedError` | Falls through to generic pipeline `except Exception` → `_fail_task` → `TASK_FAILED` with `reason=str(exc)` |
| `BudgetExceededError` | Caught explicitly in pipeline → `_block_task_on_budget` → Mission `BLOCKED` + `BUDGET_EXCEEDED` |
| `asyncio.CancelledError` | Propagates uncaught; pipeline handler transitions Mission to `CANCELLED` and releases Employee |
| `SelfCorrectionExhaustedError` (Sprint 17) | Raised after `MAX_CORRECTION_ATTEMPTS` (3) blocked terminations; caught explicitly → `_fail_task_with_reason_code(..., "self_correction_exhausted", ...)` → `TASK_FAILED` with additive `reason_code` payload field; Reviewer never reached |
| `EmployeeSurrenderedError` (Sprint 17) | Raised on an accepted `**Unable to Complete:**` marker; caught explicitly → `_fail_task_with_reason_code(..., "employee_surrendered", ...)` → `TASK_FAILED` with `reason_code`; Reviewer never reached |

Both new exceptions get their own `except` clause (not folded into `ToolLoopExhaustedError`'s generic path) so the dispatch stays uniform: raise → catch → fail-with-reason-code, per DECISIONS.md #239.

### 7.14 Self-correction (Sprint 17)

`docs/DECISIONS.md` #239–#242. The orchestrator (`run_tool_loop`) intercepts a **termination attempt** (the Employee returns no `tool_calls`) while `loop_state.last_validation_status == "failed"` — it does NOT intercept the moment `run_validation` reports failure. An Employee that reacts to its own failed check proactively, without ever trying to stop, is never intercepted and spends zero correction attempts; forced correction only fires on a blocked termination.

- **`MAX_CORRECTION_ATTEMPTS = 3`** (`orchestrator.py`, next to `MAX_DENIED_STREAK`/`MAX_MALFORMED_STREAK` — a loop-shape code constant, not `settings.*`). Checked before incrementing; the 4th blocked termination raises `SelfCorrectionExhaustedError`.
- **Surrender**: `re.search(r"\*\*Unable to Complete:\*\*", text, flags=re.IGNORECASE)` on the terminating `result.text` only — mirrors `parsing.parse_verdict`'s lenient style. Accepted even at zero prior correction attempts. Raises `EmployeeSurrenderedError`; the surrender text is bounded via `output.bound_output` before it reaches any DB row or SSE payload.
- **Corrective reminder text is a single server-owned constant**, appended as a synthetic user-turn message — never templated from raw `CheckResult` output (which could carry repository content) and never provider-supplied.
- **`revert_last_patch`** — zero-argument tool; target sha is `loop_state.apply_patch_commit_history[-2]` if ≥2 patches exist, else `context.branch_base_sha`. `WorkspaceManager.revert_last_commit` runs `git merge-base --is-ancestor` (argv-list, `shell=False`) before `git reset --hard`; ancestry failure → `WorkspaceConflictError` → handler translates to `ToolDeniedError` (denied, not destructive). Consumes one tool-call budget slot like any other tool. Post-success bookkeeping — popping the history entry, clearing `last_validation_status` — is done by the **orchestrator**, not the handler (same ownership split as the rest of `LoopState`).
- **`SELF_CORRECTION_TRIGGERED`** event: new `EventType`, bounded/structured payload (task id, agent id, attempt count — no file/patch content), published via an `on_self_correction_triggered` callback injected into `run_tool_loop` (the harness module still never imports `EventBus`, Rule #1). Fires exactly once per loop that ever entered correction (`loop_state.first_correction_emitted` guards repeats).
- **Audit**: three synthetic `HarnessToolCallORM` rows reuse `tool_name` prefix `"_loop:"` (`_loop:correction_interception`, `_loop:correction_exhausted`, `_loop:employee_surrendered`) with a new `status = "recorded"` value, written via `audit.record_loop_event` — no new table. `get_harness_summary` filters these out of `tool_call_count`/`tools_used`/`denied_count`/`error_count` and derives `correction_attempts`/`rollback_count`/`surrendered`/`exhausted` from them (plus successful `revert_last_patch` rows for `rollback_count`).
- **Both failure paths skip the Reviewer** entirely and release the Employee to `IDLE` via the same two-edge walk (§19) Sprint 16 already uses.
- **Mock coverage**: `SELF_CORRECTION_DEMO`/`SELF_CORRECTION_ROLLBACK` are real full-pipeline `mock_provider.py` scenarios (marker substring in the initial user message), paired with a test-only `_sequence_validation_statuses` helper (`test_self_correction_integration.py`) that monkeypatches `harness.sandbox_runner.run_check` in place, since the stock `FakeSandbox` keys results by profile *name* and can't express "same profile fails once, then passes." `SELF_CORRECTION_EXHAUSTED`/`SELF_CORRECTION_SURRENDER` are deliberately **not** scripted as full mock-pipeline scenarios — covered instead by orchestrator-level `FakeGateway` tests (`test_agent_harness_orchestrator.py`) plus a dedicated `test_workflow_engine_reason_code.py` for the `_fail_task_with_reason_code` plumbing (DECISIONS.md #239/#241).

### 7.15 OpenRouter provider + structured logging (Sprint 19)

**`OpenRouterProvider`** (`provider_gateway/openrouter_provider.py`, 226 lines) implements `ProviderGateway` **from scratch**, not as an `AnthropicProvider` subclass — OpenRouter always speaks the OpenAI `/v1/chat/completions` wire format regardless of the upstream model it routes to, not Anthropic's `/v1/messages` (DECISIONS.md #249 / sprint-19.md §4.2).

- `_to_openai_messages` translates Commander's `(system, messages)` shape to OpenAI's `messages` list, including the Anthropic-shaped `tool_use`/`tool_result` content blocks the Agent Harness's tool loop produces — the same tool loop runs unmodified over either provider.
- The API key is read only via `SecretsProvider.get("OPENROUTER_API_KEY")` — same choke point discipline as `ANTHROPIC_API_KEY`. Outbound headers are exactly `Authorization`, `Content-Type`, `HTTP-Referer`, `X-Title` (the latter two are fixed, deterministic attribution strings, never client input) — the CEO's `X-Request-Id` is never forwarded upstream.
- `_legible_error` mirrors `AnthropicProvider._legible_error`: a `401`/`403` becomes a plain-language `RuntimeError`; everything else (`429`/`5xx`, which the gateway's existing retry/backoff already handles, and other `4xx`) is left as the original `httpx.HTTPStatusError` for the gateway to classify normally. A `402 Payment Required` (unfunded account) is one of the "other 4xx" — surfaces as a clean `FAILED` Mission state, never a hang or raw traceback (verified against a real unfunded account during Sprint 19 Phase 3).
- `model_registry/registry.py` gained an `openrouter` map; `openai/gpt-oss-20b:free` is the default free-tier model (chosen in DECISIONS.md #249 for being both free and tool-call-capable — most free-tier models are not).
- `boot_checks.py` gained the same fail-fast-at-startup branch Anthropic already had: `COMMANDER_PROVIDER=openrouter` with no key anywhere fails before accepting traffic, not confusingly on the first Mission.

**Structured JSON logging** (`app/core/logging.py`, new file, ~75 lines) — one `JSONFormatter`, installed via `install_logging()` at the top of `main.py::lifespan`, replacing the root logger's handlers. No new logging dependency (no `structlog`, no `python-json-logger`) — Commander owns this code.

- Two independent ID scopes, not one unified correlation ID: `request_id_var` lives for one HTTP request (set by `CorrelationIdMiddleware`, `main.py`); `task_id_var`/`agent_id_var`/`project_id_var` live for one background Mission pipeline (set by `workflow_engine.py` around `_spawn`/`_run_role`/`_run_engineer_tool_loop`). Contextvars propagate through `asyncio.create_task` automatically — no plumbing needed at each `logger.info(...)` call site.
- `CorrelationIdMiddleware` is plain ASGI (`__call__(self, scope, receive, send)`), **not** `@app.middleware("http")`/`BaseHTTPMiddleware` — see the load-smoke finding below for why. It generates a server-side UUID and **never** trusts an incoming `X-Request-Id` header (Rule #7-adjacent: a client-forged header could otherwise make unrelated requests appear correlated in the logs). The ID is response-header-only and contextvar-only — never persisted to a table, never in an Event payload.
- Secret-shaped `extra={}` keys are redacted before serialization — see the substring-match fix in DECISIONS.md #251 (a Sprint 19 Phase 4 security audit found the original exact-match blocklist missed common real-world names like `api_key`/`auth_token`/`password_hash`).
- **Load-smoke finding, not a logging bug:** building `scripts/load_smoke.py`'s concurrent-SSE scenario surfaced that `httpx.ASGITransport` cannot support the realtime SSE endpoint at all (buffers the entire ASGI response before returning, incompatible with a heartbeat-until-disconnect stream) — reproducible with a single connection, unrelated to concurrency or middleware. Two real hardenings landed while chasing this red herring and are worth keeping: `CorrelationIdMiddleware` converted from `BaseHTTPMiddleware` to plain ASGI (documented issues bridging concurrent long-lived streaming responses through its internal task/memory-stream), and a redundant `request.is_disconnected()` poll removed from `realtime/routes.py` (it raced `sse_starlette`'s own `_listen_for_disconnect` task for the same one-shot ASGI `receive()` channel). The actual fix lives in the test script, not product code: `scripts/load_smoke.py` scenario 2 now drives a real `uvicorn.Server` on loopback instead of `ASGITransport`. Full detail: DECISIONS.md #250.

### 7.13 Provider tool-use plumbing

- `core/interfaces/provider_gateway.py`: `CompletionResult` gained `tool_calls: tuple[ToolCallData, ...] = ()` and `stop_reason: str = "end_turn"`. Purely additive; existing callers unaffected.
- `AnthropicProvider.complete` sends `tools` when `opts["tools"]` is present, parses `tool_use`/`text` content blocks.
- `AnthropicProvider.stream` is **untouched** — tool-loop turns use non-streaming `complete()` only (DECISIONS.md #233: intermediate harness reasoning doesn't need character-level SSE to the CEO, Rule #11).
- `MockProvider` has a deterministic 5-turn fixture: `list_repository → read_file(README.md) → apply_patch → run_validation(python-syntax) → completion`. Keyed off `len(messages)`. Rework variation added via `_is_rework()` (checks for `"CEO feedback to address"` marker) after DECISIONS.md #236 revealed the mock replayed identical content on every attempt.

---

## 8. Event Architecture

### 8.1 The envelope

`Event` (Pydantic v2, `core/events/base.py`) — immutable fact:
```
id, project_id, kind ("system"|"conversation"), type (EventType),
actor {role, id, name}, payload (dict), reason (str | None), created_at
```

### 8.2 EventBus (`modules/event_bus/bus.py`)

`InProcessEventBus.publish(event)`:
1. Persist to `events` table.
2. Fan out to in-process subscribers (`self._subscribers[event.type]`) — subscriber failure is logged, never re-raised (never breaks publish).
3. Push to every live SSE queue for the project.

`publish_transient(event)` — SSE-only, no persistence, no subscribers. Used for streaming `CONVERSATION_MESSAGE_DELTA` — persisting every chunk would flood the events table.

**No broker. Single asyncio worker. In-process fan-out.** Accepted tradeoff (CLAUDE.md §15). Future extraction point is a broker-backed Event Service.

### 8.3 Event families

See `core/events/types.py`. Notable:
- **Reviewer verdict is provider-agnostic** — parsed from the trailing `**Verdict:**` line by `parsing.parse_verdict`. This is the ONE hard contract in the pipeline; workflow logic must not branch on provider-specific response formatting.
- **`kind: system | conversation`** affects rendering, not storage (Rule #8: Timeline is derived from ONE event stream).
- Ordering: `EventORM.seq` (autoincrement PK) is authoritative order; `EventORM.id` (UUID) is the dedup key the frontend uses.
- **Sprint 16 did NOT add a per-tool-call event** — deliberate. `HarnessToolCallORM` is the durable record; `GET .../harness-summary` is the aggregate view.
- **Sprint 18 added `MEMORY_RECORDED`** (published once per real insert into `memory_records`, by `memory/service.record_memory` — never on a dedup-skipped duplicate) **and `MEMORY_RECALLED`** (published by `PlanningOrchestrator._maybe_recall` every time a PM turn's `recall_request` fires, including zero-match attempts, carrying `spec_id`/`requested_categories`/`match_count`/`memory_ids` — no content bodies).

---

## 9. Database / Persistence Architecture

- Postgres by default (via `docker-compose`), SQLite for tests (temp file per fixture — `conftest.Harness`).
- Alembic owns the schema. **`alembic/versions/` is authoritative.** Never create tables at runtime except in tests (`Base.metadata.create_all`) — do not confuse "works in tests" with "works after a real migration."
- Each `_run_pipeline` stage **opens its own session**. Never hold an ORM object across an `await` on the provider (CLAUDE.md §9.3). `TaskSnapshot` (frozen dataclass) is threaded through instead of the ORM row itself.
- SQLite and Postgres do not agree on `DateTime(timezone=True)`: SQLite returns naive datetimes. Every timezone comparison must normalize (see `engine._check_budget`, `auth_service.resolve_session`, `employee_resolution._tie_break_key`).
- FK cycle: `tasks.specification_id ↔ specifications.source_task_id`. Resolved via `use_alter=True` in `db_models.py`. If you add another cycle, remember `create_all`/`drop_all` order matters.
- `IntegrityError` is a DB-level guarantee, not a service-layer check. Both `role_singleton_locks` and `active_specification_locks` use PK constraints (composite / single) to make concurrent inserts race-safe. Losing inserts catch `IntegrityError` and map to `SingletonRoleViolation`/`ActivePlanningExistsError` → HTTP 409.

---

## 10. Frontend Architecture

- Next.js App Router, TypeScript, Tailwind, TanStack Query. Dark, Render-inspired.
- `/company/[id]` is the CEO Workspace. Registry-driven (Sprint 15) — `WorkspaceWidgetGrid` renders whichever widgets the CEO's `workspace_preferences` marks visible, in the CEO's own order. `PrimaryActionPanel` renders the server's `next_action` **verbatim** — do NOT recompute it client-side (that would create a second, driftable copy of the precedence rules).
- One SSE connection per Company. `RealtimeProvider` is keyed on `companyId` so switching Companies remounts state.
- Every API call sends `credentials: "include"`. Any 401 dispatches a `commander:unauthorized` window event that `AuthProvider` catches to clear state and redirect to `/login`. `lib/api.ts` has no React/router dependency.
- Generated TS event types live in `packages/event-schemas/ts/`. **Never hand-edit.** Regenerate after event schema changes: `python scripts/generate_ts_schemas.py`.
- Widget error isolation: each widget wrapped in a `WidgetErrorBoundary`. The `primary_next_action` slot has a stronger non-dismissable fallback (DECISIONS.md #231).
- Rule #18 (no silent failure): every CEO mutation must succeed or surface a visible error. `ToastProvider` + `ApiStatusBanner` cover this. Do not swallow API errors client-side.

Key mapping backend→frontend:
| Backend | Frontend |
|---|---|
| `WorkspaceSnapshot` | `useWorkspaceOverview` → `WorkspaceWidgetGrid` |
| `next_action` | `PrimaryActionPanel` — verbatim |
| `HarnessToolCallORM` (via `GET .../harness-summary`) | **not surfaced yet** |
| `CODE_CHANGED` payload | `MissionDetail.tsx` (`code_stats`, `check_results`) |
| `CONVERSATION_MESSAGE_DELTA` (transient) | `ChatThread.tsx` streams |
| `SPECIFICATION_*` events | `SpecificationDetail.tsx` (via `invalidateForEvent` with `specificationId`) |

---

## 11. Security Model

### 11.1 Trust boundary

Everything outside this server process's trusted template/config code is untrusted: raw provider output (including `tool_use` name/arguments), file paths, patch content, search patterns, validation-profile parameters, repository file contents, sandboxed tool output, environment variables, DB-stored skill-template/RoleSpec values. Only `TEMPLATE` (`software_company.py`) and the immutable `TOOLS_BY_KEY` registry are trusted sources of what a tool *can* mean. **Default posture is deny.**

### 11.2 Execution isolation

- **`SandboxRunner` is the ONLY place AI-generated content is ever executed.** The command itself (`CheckSpec.command`) is trusted template data — never AI output. Only the *presence* of matching files selects which commands run.
- `DockerSandbox`: `--network none`, `--memory 512m`, `--cpus 1`, `--pids-limit 256`, non-root (`--user 10001:10001`), `--cap-drop ALL`, `--security-opt no-new-privileges`, 120s hard timeout with process-tree kill (`docker kill <container>`; `finally: docker rm -f`), 10 KB output tail. `--read-only` is deliberately NOT set (checks legitimately write `__pycache__`/coverage/`node_modules/.cache`).
- Fails closed: no Docker, no image, daemon down, timeout, OOM → `CheckResult(status="could_not_run", ...)` with a plain-language reason. Never raises past `SandboxRunner`.
- Capability probed via `docker info` + `docker image inspect`, cached for 5 s.

### 11.3 Authorization

- Session cookie authentication (HttpOnly, `samesite=lax`), SHA-256 token hash at rest, sliding 7-day expiry capped at 30-day absolute.
- `get_current_user` dependency on **every** router except `health` and `auth`.
- `commander_cookie_secure` gates the `Secure` flag — dev serves http (False by default); any TLS deployment must set it, or the browser drops the cookie.
- Cross-account access returns **404, not 403** (Rule #15). Existence is not disclosed. `core.ownership.project_owned_by` / `resource_owned_by` are the enforcement points.

### 11.4 Secrets

- `SecretsProvider` port (`core/secrets.py`) is the ONLY path to values like `ANTHROPIC_API_KEY`.
- `DBSecretsProvider` reads `settings_kv` override → `.env` fallback.
- Never log a secret value, never return one through an API, never echo one into a prompt, never commit one.
- `redact_environment_like_content` in `agent_harness/output.py` is defense-in-depth for accidental secret-shaped lines in tool output. The **primary** control is that harness handlers never read process environment.
- `scripts/export_users.py` never touches `password_hash`.

### 11.5 Path safety

- `validate_path` in `workspace_manager/validation.py`: rejects empty, drive-letter, absolute, `..`-containing, `.git/`-rooted paths; `.resolve()` + `.relative_to(repo_root)` — genuine confinement (not string-prefix).
- `agent_harness/guards.py::guard_path` additionally rejects a target that is itself a symlink (confused-deputy defense).
- Content: NUL byte forbidden; 256 KiB max.
- Symlink policy: `.resolve()` follows symlinks in existing components → the escape check triggers → violation.

### 11.6 The harness security guarantees (Sprint 16)

1. Tools are code-owned and immutable (`registry.py`).
2. Permission is a fail-closed intersection re-derived on every call.
3. Provider cannot self-grant tools (unknown tool → deny).
4. Every tool call is schema-validated (`extra="forbid"`).
5. Workspace root is server-selected (`ToolRunContext.repo_root`).
6. Absolute/traversal/prefix-confusion/non-existent-target/symlink-escape paths all denied.
7. Writes only through the structured `apply_patch` tool; pre-validated whole-patch atomicity.
8. Binary/special-file mutation denied (NUL byte + symlink checks).
9. Validation profiles named only; no arbitrary executable or flags.
10. Every process uses `shell=False` (audited — zero `os.system`/`shell=True`/`create_subprocess_shell` in `apps/api/app/`).
11. Timeouts kill process trees (`docker kill` at container level, not one PID).
12. Environment is minimized (no `--env` flags passed to `docker create`).
13. Tool timeouts + output truncation + secret-shape redaction.
14. Calls idempotent by `call_id`; duplicate replay never re-executes.
15. Cancellation prevents further calls (BaseException propagation).
16. Validation failure never silently marks Mission successful (it's Reviewer evidence, not a gate).
17. Audit records durable and safe (content-free `arguments_summary`).
18. **No public arbitrary tool endpoint exists.** The only harness-adjacent public route is the read-only `GET /api/tasks/{id}/harness-summary`.

### 11.7 Residual risk (honestly recorded)

- The DockerSandbox is **application-level isolation on Docker Desktop**. It is not proven OS-grade sandboxing. DECISIONS.md #238 (residual limitations): do not overclaim.
- `--read-only` deliberately not set — checks legitimately write under `/workspace`.
- `run_validation` returns `could_not_run` when Docker is unavailable — same Sprint 6 tradeoff, unchanged by Sprint 16.
- No employee-firing flow, so `role_singleton_locks` rows are never deleted.

---

## 12. Important Architectural Decisions

Each entry: **Decision · Why · Affected systems · What NOT to casually change.**

### 12.1 Everything is an Event; Timeline is one stream (Rule #8)
- **Why:** single storage model, single audit trail, Project Memory (Sprint 18 — `app/modules/memory/`) projects over this one stream instead of reconciling two.
- **Affected:** `event_bus`, `timeline`, `reports`, `realtime`, `agent_harness` (deliberately does NOT emit per-call events).
- **Don't:** create a second event-like table for "engineering-only" facts. `HarnessToolCallORM` is intentionally an **audit** table, not a competing event stream; it is not on the Timeline.

### 12.2 Roles are data, Employees are instances (Rule #16)
- **Why:** adding Designer/QA/DevOps must be a template-data change, never an engine change. Multiple Employees per Role must be supported.
- **Affected:** `templates/`, `agent_runtime`, `workflow_engine`, `prompt_builder`, `agent_harness`. Every consumer branches on `RoleSpec` fields or `StageSpec.kind`.
- **Don't:** write `if role_key == "engineer":` anywhere except `app/templates/`. `test_role_hardcoding_guard.py` is an AST-walking test — a comment-line match won't help; the code has to actually not use the pattern.

### 12.3 Providers are replaceable (Rule #4)
- **Why:** worker interchangeability is the whole product thesis.
- **Affected:** `provider_gateway`, `model_registry`, workflow (uses only `ProviderGateway`).
- **Don't:** import `anthropic_provider` directly outside `provider_gateway/`. Do not read `settings.anthropic_api_key` outside `SecretsProvider`.

### 12.4 CEO's only conversational counterpart is the PM (Rule #11)
- **Why:** organizational integrity. "It's a company." No `/api/chat/engineer` route exists or should exist.
- **Affected:** `tasks/service.post_message` (always routes to PM unless a Mission is assigned to a specific Employee), `planning` (CEO only interacts via the PM's counterpart role), UX_SPEC §3.
- **Don't:** add any CEO→CTO or CEO→Engineer direct channel.

### 12.5 Autonomous loops are budgeted (Rule #13)
- **Why:** never retry forever, never silently stop.
- **Affected:** `_check_budget` (mission budget), `HarnessBudget` (tool loop), `MAX_PLANNING_TURNS`/`MAX_MALFORMED_ATTEMPTS` (planning).
- **Don't:** add a new loop without a budget. Never silently retry.

### 12.6 Tools are granted by the Template to a Role (Rule #12)
- **Why:** whitelist-based security model. AI can never obtain a shell.
- **Affected:** `agent_harness/registry.py`, `RoleSpec.tools`, `SkillTemplate.capabilities`, `permissions.resolve_permitted_tools`.
- **Don't:** add a `run_shell`/`install_package`/`network_fetch` tool. Do not read tool definitions from the DB or from provider output. Free shell execution is permanently rejected.

### 12.7 `apply_patch` commits immediately, not deferred (DECISIONS.md #234)
- **Why:** every read tool resolves through a committed ref (`git ls-tree`/`git show ref:path`/`git diff ref...ref`). An uncommitted write would be invisible to the Engineer's own next read in the same loop.
- **Affected:** `agent_harness/handlers.apply_patch`, `_land_tool_loop_changes` (uses `diff_stats` not `commit()`), `WorkspaceManager.diff_stats`.
- **Don't:** revert to per-attempt single-commit. The one-shot path still uses one commit; the tool-loop path uses one commit per successful `apply_patch`.

### 12.8 Singleton hiring is DB-enforced, not service-layer
- **Why:** service-layer check-then-insert has a TOCTOU race under concurrency.
- **Affected:** `RoleSingletonLockORM` (composite PK), `hire_employee`, `create_department`. Analogous pattern for planning: `ActiveSpecificationLockORM`.
- **Don't:** revert to check-then-insert. `IntegrityError → SingletonRoleViolation` is the whole race safety.

### 12.9 Cross-account access returns 404, not 403 (Rule #15)
- **Why:** existence disclosure is a real leak.
- **Affected:** every route (`project_owned_by`/`resource_owned_by`).
- **Don't:** return 403 anywhere for cross-account. Do not check ownership inside a service function; the route is the gate.

### 12.10 Sprint-16 audit split: durable audit table + coarse Timeline (DECISIONS.md #233/#237)
- **Why:** per-call Timeline events would flood the CEO's narrative with engineering minutiae. The audit table is engineering evidence; the Timeline is CEO evidence.
- **Affected:** `HarnessToolCallORM`, `get_harness_summary`, all `agent_harness/*` — no `EventBus.publish` inside a handler.
- **Don't:** add per-call Timeline events "just in case." If you need finer CEO-visible detail, add a bounded aggregate route, not a stream.

### 12.11 PlanningOrchestrator is per-call, WorkflowEngine is a singleton
- **Why:** planning turn bursts run to completion inside one awaited call; missions run in a background `asyncio.Task` that needs a registry (`_running`) for `cancel()` and orphan recovery.
- **Affected:** `planning/orchestrator.py` (constructed fresh in `service`), `workflow_engine/engine.py` (constructed once in `main.py::lifespan`).
- **Don't:** invert either — you would break either cancel semantics or the "no state between calls" simplification.

### 12.12 In-process EventBus, single worker, plaintext secrets in DB
- **Why:** local-MVP tradeoffs, explicitly accepted (CLAUDE.md §15).
- **Affected:** deployment story. `docs/DECISIONS.md` records the future extraction points.
- **Don't:** "fix" these opportunistically. Any move to a broker-backed EventBus is a scoped sprint of its own.

### 12.13 Self-correction is termination-triggered, and rollback is server-computed (DECISIONS.md #239–#242)
- **Why:** forcing correction the instant a check fails would penalize an Employee that was already about to fix it in its own next turn; only intercepting a blocked *termination* attempt means proactive self-correction never costs a budgeted attempt. Separately, a rollback tool that trusted any provider-supplied target/branch would reopen exactly the arbitrary-write risk Rule #9/#12 exist to close.
- **Affected:** `agent_harness/orchestrator.py` (interception + `MAX_CORRECTION_ATTEMPTS`), `agent_harness/handlers.py::revert_last_patch` (zero-argument schema, server-computed target), `workspace_manager/local_git.py::revert_last_commit` (ancestry check before reset).
- **Don't:** move the failure check to fire eagerly inside `run_validation`. Don't add any argument to `revert_last_patch`'s schema, or accept a target sha/branch from provider output. Don't skip the `git merge-base --is-ancestor` check "for efficiency" — it's the only thing standing between a denied rollback and a destructive one on a tampered `branch_base_sha`.

### 12.14 Project Memory recall is PM-explicit-only and deterministic-only (DECISIONS.md #245–#247)
- **Why:** an automatic "inject relevant memory into every turn" design would make the pipeline's prompt cost unpredictable and unbudgeted (Rule #13 tension), and letting recall call an LLM for relevance scoring would make a supposedly-observable projection stage behave nondeterministically. Gating recall on an explicit PM `recall_request` field keeps it opt-in and keeps `MAX_RECALL_*` a hard, predictable cap; keeping the whole read path (projection AND recall) LLM-free keeps it testable with plain assertions.
- **Affected:** `app/modules/memory/` (all of it — `registry.py`, `projection.py`, `service.py`, `subscriber.py`, `backfill.py`), `planning/orchestrator.py` (`_validate_recall_request_optional`, `_reject_recall_request`, `_maybe_recall`, `pending_recall_message`).
- **Don't:** add a code path where `_maybe_recall` fires without a PM turn having set `recall_request`. Don't route any extractor or `recall()` call through `ProviderGateway` — Memory must stay a pure projection over `events`, never a second inference surface. Don't let a CTO turn's `recall_request` field survive parsing — `_reject_recall_request` must keep failing that case at parse time, not by a runtime `if role == "cto"` check (Rule #16).

### 12.15 `OpenRouterProvider` is a fresh `ProviderGateway` implementation, not an `AnthropicProvider` subclass (DECISIONS.md #249)
- **Why:** OpenRouter always speaks the OpenAI `/v1/chat/completions` wire format regardless of which upstream model it's routing to — subclassing `AnthropicProvider` would mean overriding almost every method just to swap the wire format, which is more fragile than a from-scratch sibling implementation of the same `ProviderGateway` port.
- **Affected:** `provider_gateway/openrouter_provider.py` (new), `model_registry/registry.py` (`openrouter` map), `config.py` (`commander_provider` literal extended, `openrouter_api_key` field), `secrets.py` (`OPENROUTER_API_KEY` in `_ENV_DEFAULTS`), `boot_checks.py` (OpenRouter branch).
- **Don't:** read `settings.openrouter_api_key` anywhere outside `secrets.py` (except `boot_checks.py`'s presence-only truthiness check). Don't forward the CEO's `X-Request-Id` header to OpenRouter — only `Authorization`/`Content-Type`/`HTTP-Referer`/`X-Title` are sent, and the latter two are fixed strings, never client input.

### 12.16 Correlation ID middleware is plain ASGI, not `BaseHTTPMiddleware` (DECISIONS.md #250)
- **Why:** `@app.middleware("http")` decorator sugar produces a `BaseHTTPMiddleware` instance, which bridges every response body through its own internal task + memory stream — this has documented issues with long-lived streaming responses under concurrent load. A plain ASGI middleware class (`__init__(self, app)` / `async def __call__(self, scope, receive, send)`) passes `receive`/`send` straight through, so it composes safely with any number of concurrent SSE connections.
- **Affected:** `main.py`'s `CorrelationIdMiddleware`.
- **Don't:** revert this to `@app.middleware("http")` sugar "for readability" — it was specifically converted away from that shape while diagnosing a load-smoke SSE hang (which turned out to have a different root cause entirely — `httpx.ASGITransport`, a test-harness limitation, not this middleware — but the ASGI conversion is a real, independent hardening worth keeping).

---

## 13. Non-Negotiable Invariants

Break any of these and Commander is no longer Commander:

1. **Modules never import each other's internals.** EventBus + public functions + shared core infra only.
2. **Agents never talk to each other directly.** Always via events and workflow state.
3. **Every significant action emits an event with a `reason`.** Rule #3.
4. **ProviderGateway is the only path to AI.** No SDK imports outside `provider_gateway/`.
5. **Mock mode always works with zero API keys.** `COMMANDER_PROVIDER=mock` is not degraded; it's a first-class provider.
6. **Secrets flow through `SecretsProvider` only.** Never logged, never in an API response, never in a prompt.
7. **Timeline is one event stream.** `kind` affects rendering, not storage.
8. **AI-generated code is never freely executed.** Only trusted `CheckSpec.command`s, only inside the sandbox.
9. **Any architecture change updates CLAUDE.md + `docs/ARCHITECTURE.md` in the same commit.** Rule #10.
10. **CEO has exactly one conversational counterpart: the PM.** No CEO→CTO/Engineer/Reviewer route may exist.
11. **Tools are granted by the Template to a Role.** Nobody else grants tools. Whitelist, not blocklist. Free shell is permanently rejected.
12. **Autonomous loops are budgeted.** Every loop has iteration/token/wall-time bounds.
13. **Project Memory is derived from events.** No second source of truth.
14. **All data access is account-scoped.** Cross-account → 404, never 403.
15. **Roles are data; Employees are instances.** No hardcoded role names in engine/prompt/component code.
16. **New CEO capabilities enter through Widgets or Sidebar pages.** Never bolted onto the PM conversation.
17. **CEO actions never fail silently.** Every mutation succeeds or fails with a visible explanation.

Sprint 16 harness-specific:
- Tool registry is immutable and code-owned.
- Permission is a fail-closed AND across five terms.
- Provider cannot self-grant a tool.
- Every tool call is schema-validated before authorization.
- Every process uses `shell=False`.
- Workspace root is server-selected.
- Writes only through the structured `apply_patch` tool with atomic-or-rollback semantics.
- `run_validation` accepts a profile *name* only; commands and executables are template-owned.

Sprint 17 self-correction-specific:
- Correction is bounded at `MAX_CORRECTION_ATTEMPTS = 3` — never retried a 4th time.
- Correction interception fires only on a blocked termination attempt, never eagerly on validation failure.
- `revert_last_patch` takes zero provider-supplied arguments; its target commit is always server-computed and ancestry-checked before any destructive git operation.
- Surrender text is bounded (`output.bound_output`) before it reaches any DB row or SSE payload.
- No path exists from `last_validation_status == "failed"` to a successful Mission outcome without either a corrective fix, exhaustion-failure, or surrender-failure.
- Both new failure paths (`self_correction_exhausted`, `employee_surrendered`) skip the Reviewer entirely.

Sprint 18 memory-specific:
- `memory_records` has a DB-level `UNIQUE(source_event_id)`; that constraint — not any in-code check — is the entire dedup guarantee shared by the live subscriber and by `backfill_memory`.
- Every extractor in `projection.py` is zero-LLM and returns `None` on any malformed/missing input rather than raising.
- `recall()` always applies server-side caps (`MAX_RECALL_LIMIT` etc.) regardless of what the PM's `recall_request` asks for, and always scopes to the calling Company's `project_id`.
- A CTO turn's JSON is structurally rejected if it carries a non-null `recall_request` (`_reject_recall_request`, parse-time, not a runtime role check).
- `MEMORY_RECALLED` publishes on every recall attempt, including zero-match ones.

---

## 14. Critical Files / Where To Look

### 14.1 Backend

| Concern | Path |
|---|---|
| API entrypoint / wiring | `apps/api/app/main.py`, `apps/api/app/deps.py` |
| Ports | `apps/api/app/core/interfaces/` |
| Event envelope + types | `apps/api/app/core/events/{base,types,contracts}.py` |
| ORM tables | `apps/api/app/core/db_models.py` |
| State machines | `apps/api/app/core/lifecycle/` |
| Secrets | `apps/api/app/core/secrets.py` |
| Ownership | `apps/api/app/core/ownership.py` |
| Errors | `apps/api/app/core/errors.py` |
| The one template | `apps/api/app/templates/software_company.py` |
| Workflow engine | `apps/api/app/modules/workflow_engine/engine.py` |
| Workflow parsing (verdict, FILE blocks) | `apps/api/app/modules/workflow_engine/parsing.py` |
| Employee resolver | `apps/api/app/modules/workflow_engine/employee_resolution.py` |
| Planning orchestrator | `apps/api/app/modules/planning/orchestrator.py` |
| Planning service (approval gate) | `apps/api/app/modules/planning/service.py` |
| Memory category registry + constants | `apps/api/app/modules/memory/registry.py` |
| Memory extractors (pure, zero-LLM) | `apps/api/app/modules/memory/projection.py` |
| Memory writer + recall reader | `apps/api/app/modules/memory/service.py` |
| Memory live EventBus subscriber | `apps/api/app/modules/memory/subscriber.py` |
| Memory backfill (idempotent) | `apps/api/app/modules/memory/backfill.py`, `scripts/backfill_memory.py` |
| Agent Harness | `apps/api/app/modules/agent_harness/` — **read all 11 files** |
| Tool registry | `apps/api/app/modules/agent_harness/registry.py` |
| Permission intersection | `apps/api/app/modules/agent_harness/permissions.py` |
| Tool orchestrator | `apps/api/app/modules/agent_harness/orchestrator.py` |
| Tool handlers + dispatch | `apps/api/app/modules/agent_harness/handlers.py` |
| Audit persistence | `apps/api/app/modules/agent_harness/audit.py` |
| Path guards | `apps/api/app/modules/agent_harness/guards.py` |
| Output bounding + redaction | `apps/api/app/modules/agent_harness/output.py` |
| Budget | `apps/api/app/modules/agent_harness/budget.py` |
| Workspace manager (git I/O) | `apps/api/app/modules/workspace_manager/local_git.py` |
| Path validation | `apps/api/app/modules/workspace_manager/validation.py` |
| DockerSandbox | `apps/api/app/modules/sandbox/docker_sandbox.py` |
| ProviderGateway (retry, model resolve) | `apps/api/app/modules/provider_gateway/gateway.py` |
| MockProvider | `apps/api/app/modules/provider_gateway/mock_provider.py` |
| AnthropicProvider | `apps/api/app/modules/provider_gateway/anthropic_provider.py` |
| EventBus | `apps/api/app/modules/event_bus/bus.py` |
| Mission service (create/assign/cancel/orphan recovery/harness-summary) | `apps/api/app/modules/tasks/service.py` |
| Workspace snapshot | `apps/api/app/modules/workspace_overview/service.py` |
| Next-action policy (pure function) | `apps/api/app/modules/workspace_overview/next_action.py` |
| Widget registry | `apps/api/app/modules/workspace_widgets/registry.py` |
| Migrations | `apps/api/alembic/versions/` (head: `c2a7e1f4b6d3` — adds `memory_records`, `down_revision = 'b1f4c8d5e9a2'`) |
| OpenRouterProvider | `apps/api/app/modules/provider_gateway/openrouter_provider.py` |
| Structured JSON log formatter + contextvars | `apps/api/app/core/logging.py` |
| Correlation ID middleware | `apps/api/app/main.py` (`CorrelationIdMiddleware`) |
| Load smoke (4 scenarios) | `scripts/load_smoke.py` |
| Real-LLM verification (multi-provider) | `scripts/verify_real_llm.py` (`--provider anthropic\|openrouter`) |

### 14.2 Frontend

| Concern | Path |
|---|---|
| CEO Workspace page | `apps/dashboard/app/company/[id]/page.tsx` |
| Widget shell | `apps/dashboard/components/workspace/WorkspaceWidgetGrid.tsx` |
| Widget→component mapping | `apps/dashboard/components/workspace/widgetComponents.tsx` |
| Primary-action panel (renders `next_action` verbatim) | `apps/dashboard/components/workspace/PrimaryActionPanel.tsx` |
| Mission detail (code_stats, check_results) | `apps/dashboard/components/MissionDetail.tsx` |
| Specification detail | `apps/dashboard/components/SpecificationDetail.tsx` |
| SSE event handling | `apps/dashboard/lib/useEventStream.ts` |
| REST client | `apps/dashboard/lib/api.ts` |
| Auth context | `apps/dashboard/lib/auth-context.tsx` |
| Generated TS event types | `packages/event-schemas/ts/` — do not hand-edit |

### 14.3 Docs

- `CLAUDE.md` — hard rules (18 numbered).
- `docs/ARCHITECTURE.md` — target + as-built; §4.5 is the current Agent Harness section (rewritten in Sprint 16 Phase 5 for accuracy — DECISIONS.md #238); §5 is the current Project Memory section (rewritten as-built in Sprint 18 — DECISIONS.md #245–#247).
- `docs/DECISIONS.md` — 251 numbered entries as of Sprint 19; Sprint 16 spans #233–#238, Sprint 17 spans #239–#242, Sprint 18 spans #243–#247, Sprint 19 spans #249–#251.
- `docs/design/UX_SPEC.md` — CEO experience source of truth; unchanged by Sprint 18 or Sprint 19 (both explicitly no-new-UI sprints).
- `docs/DEPLOYMENT.md` — new in Sprint 19; the sole operational reference (first deployment, production run recipe, backup/restore, v1.0.0→v1.1 upgrade path).
- `docs/KNOWN_ISSUES.md` — new in Sprint 19; every accepted tradeoff, every deferred scope boundary, and the load-smoke-verified operating envelope in one place.
- `CHANGELOG.md` — new in Sprint 19; the v1.1.0 feature summary across Sprints 9–19.
- `PROGRESS.txt` — live checkpoint file.
- `docs/prompts/sprint-16.md`, `sprint-17.md`, `sprint-18.md`, `sprint-19.md` — the sprint briefs. Read like specs, not task lists.

---

## 15. Critical Tests

- **`tests/test_role_hardcoding_guard.py`** — AST walk that fails CI if any file in `app/` (except `app/templates/`) branches on a hardcoded role name or indexes a roles collection by position. This is the enforcement of Rule #16. Also verifies the guard actually fires (`test_the_guard_actually_detects_a_real_violation`).
- **`tests/test_agent_harness_permissions.py`** — fail-closed intersection. Uses explicit `UNGRANTED_ROLE`/`EMPTY_TEMPLATE` fixtures (not the stock `GENERALIST`), so future template edits cannot silently break the fail-closed guarantee.
- **`tests/test_agent_harness_guards.py`** — absolute/traversal/`.git`/symlink-escape/direct-symlink-target. Two symlink cases skip on Windows without symlink privilege (honestly recorded per CLAUDE.md §16.7).
- **`tests/test_agent_harness_handlers.py`** (16 tests) — bounded list/read/search, path-escape rejection, whole-patch rejection on any violation, stale-conflict (`expected_content`), `run_validation` execution-disabled/unknown-profile/success paths, `dispatch_tool_call` lifecycle (every outcome writes exactly one audit row with correct status).
- **`tests/test_agent_harness_orchestrator.py`** (8 tests) — deterministic FakeGateway drives the loop: read→patch→validate→complete, denied streak exhaustion, streak reset on intervening success, malformed streak exhaustion, duplicate `call_id` never re-dispatched (with `apply_patch` — proves no double-write), tool-call and wall-time budget exhaustion, uncaught cancellation.
- **`tests/test_agent_harness_audit.py`** — `arguments_summary` content-free-ness, one audit row per outcome.
- **`tests/test_code_missions.py`** — end-to-end code Mission (`deliverable_type="code"`). Since `ENGINEER.harness = "tool_loop"`, this now exercises the tool-loop path for free.
- **`tests/test_reliability.py`** — orphan recovery, cancel, budget guard. `test_cancel_running_mission_transitions_to_cancelled_and_frees_agent` runs the tool-loop path.
- **`tests/test_planning_orchestrator.py`** / **`test_planning_api.py`** — PM↔CTO turn loop, budget exhaustion, malformed output retry, DB race safety.
- **`tests/test_specification_orm_constraints.py`** — the FK cycle between `tasks` and `specifications`.
- **`tests/test_employee_singleton.py`** — DB-race-safe singleton hiring via `IntegrityError`.
- **`tests/test_workspace_next_action.py`** — pure-function next-action policy, unit-testable without DB.
- **`tests/test_workspace_path_safety.py`** — the primary path-safety proof (harness guards layer on top).
- **`tests/test_sandbox.py`** — DockerSandbox capability probing and `run_check` fail-closed behavior.

Test harness pattern (`conftest.py`):
- `Harness` fixture: sqlite temp file, `LocalGitWorkspaceManager` in tmp dir, `FakeSandbox`, real EventBus + AgentRuntime + WorkflowEngine. Never touches Docker or dev DB.
- `api_client` fixture: real FastAPI app via `httpx.ASGITransport`, `Depends` overrides to point at the `Harness`. Exercises the real route layer including auth/ownership.
- `settings.commander_pacing_enabled = False` set at collection time — production has 0.5–1.5s pacing sleeps for UX; tests would take ~230s with them on.

---

## 16. Known Problems / Technical Debt

Only concrete, evidence-based issues:

1. **No CEO-facing surface for `harness-summary`.** The endpoint exists but nothing renders it (DECISIONS.md #237). Deliberate for Sprint 16; Sprint 17+ decision.
2. **No employee-firing flow.** `role_singleton_locks` rows are never deleted (§6.5 accepted, docs/prompts/sprint-11.md §9). A CTO fired today re-hires as a duplicate lock conflict — no code path exercises this yet because there's no firing route.
3. **Merge conflicts leave the Mission `BLOCKED` with no CEO-facing resolution UI.** `_block_task_on_merge_failure` sets state and publishes an event with the error, but there's no widget or dashboard flow to resolve the conflict — the CEO must intervene at the filesystem.
4. **`_run_pipeline` still catches `except Exception`** for pipeline-level failures. It correctly re-raises `CancelledError` and catches `BudgetExceededError` explicitly, but other failures bucket into `_fail_task` with `reason=str(exc)`. Fine for now; if you're changing this, preserve the CancelledError separation.
5. **`WorkspaceManager.diff` truncation is by char count**, `output.bound_output` truncates by UTF-8 byte count. Two different truncation semantics coexist; both are correct for their use case but future code should not confuse them.
6. **`FakeSandbox` behavior in tests** does not exercise real Docker isolation — treat `test_sandbox.py` as the boundary test and everything else as "sandbox behaves as configured."
7. **Naïve datetime handling** appears in several places to bridge SQLite/Postgres. Pattern: check `.tzinfo is None`, `.replace(tzinfo=timezone.utc)`. If you add a new column of `DateTime(timezone=True)`, expect to add another normalization.
8. **`AnthropicProvider.stream` deliberately does not support tool_use.** Any future streamed tool-loop turn would require SSE tool_use parsing that doesn't exist yet.
9. **Mock provider's tool-loop fixture is keyed off `len(messages)`.** It's deterministic and simple, but it's not a real behavioral model — do not reason about a real Anthropic loop from `_tool_loop_response`'s branch structure. Rework variation is a marker-string check on the initial user message (`"CEO feedback to address"`), added as a test-fixture correction (DECISIONS.md #236), not product behavior.
10. **Windows symlink tests skip.** `test_agent_harness_guards.py` has 2 skips on Windows without symlink privilege. Honestly reported per CLAUDE.md §16.7. If you run on Linux, expect the count to drop to 4 skips.

---

## 17. Documentation vs Code Discrepancies

- `docs/ARCHITECTURE.md` §4.5 was **rewritten in Sprint 16 Phase 5** (DECISIONS.md #238) to fix drift where it still described `run_checks` (the tool is `run_validation`) and "every tool call emits an event" (the actual design is: coarse stage-boundary events + `HarnessToolCallORM` durable audit + `GET .../harness-summary` aggregate). It is now accurate. Do not revert.
- CLAUDE.md still describes `Sprint 4.5-tier resolution` in a couple of places — the resolution tiers are correct; the "Sprint 4.5" nomenclature is historical shorthand.
- `docs/backend/workflow/*` are older per-file design notes from V1. They are correct on lifecycle direction but predate Sprint 9's `TaskSnapshot` refactor and Sprint 16's harness. **When in doubt, read the code, not these files.**
- README §"Architecture at a glance" describes V1 accurately but does not mention the harness. The `Status` line at the top does mention Sprint 15; the README predates Sprint 16.
- `docs/design/UX_SPEC.md` was not updated in Sprint 16 (Phase 5 confirmed: no CEO-facing UI change this sprint). If you add a widget for harness-summary in Sprint 17+, this must be updated in the same commit as the widget (Rule #10).

---

## 18. Sprint 16 Handover

### What Sprint 16 achieved

- New module `app/modules/agent_harness/` (11 files, all under docstrings that cite CLAUDE.md rules and DECISIONS.md entries).
- New table `harness_tool_calls` (migration `b1f4c8d5e9a2_harness_tool_calls`).
- `RoleSpec.harness` gained value `"tool_loop"` (only `ENGINEER` uses it today).
- `ENGINEER.tools` populated with the six tool keys; all three `SkillTemplate`s gained capability `"repository_tools"`.
- `TEMPLATE.tool_loop_contracts` added (mirrors `PLANNING_CONTRACTS`) — Rule #16 preserved.
- `WorkspaceManager` port gained `repo_root(project_id)` and `diff_stats(project_id, branch_name)` methods.
- `ProviderGateway`'s `CompletionResult` gained additive `tool_calls`/`stop_reason` fields; `AnthropicProvider.complete` sends `tools` and parses `tool_use` blocks; `MockProvider` gained a deterministic 5-turn fixture.
- New `_run_engineer_tool_loop` + `_land_tool_loop_changes` in `workflow_engine/engine.py`; the produce stage branches on `role_spec.harness == "tool_loop" and task.deliverable_type == "code"`.
- New error types: `ToolDeniedError`, `ToolPathViolationError`, `ToolCallMalformedError`, `PatchConflictError`, `ToolLoopExhaustedError`.
- New config: `commander_harness_enabled`, `commander_harness_max_tool_calls` (40), `commander_harness_max_seconds` (600), `commander_harness_max_output_bytes` (16 KiB).
- New route: `GET /api/tasks/{task_id}/harness-summary` (bounded aggregate).
- 74 new tests in `test_agent_harness_*.py`. Final suite: 455 passed / 6 skipped.

### What was validated (honestly)

- Full pytest suite: green (455 passed).
- Dashboard `tsc --noEmit` + `next build`: green (all 19 routes).
- Migration round-trip and fresh Postgres bootstrap via `scripts/seed.py`: green (5 missions including a tool-loop code mission and a tool-loop rework cycle).
- Mock E2E with zero provider keys: green.
- **Browser verification: classified as UNVERIFIED** — Sprint 16 introduced no CEO-facing UI changes (Phase 4 decision), so there was nothing new to browser-verify.
- Independent 12-item security audit: all PASS.

### What Sprint 17 should be aware of (superseded — see the Sprint 17 addendum below)

- **The harness summary widget is a natural Sprint 18 addition.** The endpoint and read model exist (now including Sprint 17's correction/rollback fields); add a `harness_summary` widget key to `workspace_widgets/registry.py` and a component in `components/workspace/`.
- **Project Memory (Sprint 18)** will project over the event stream. Everything the harness does that matters (`CODE_CHANGED`, `EXECUTION_COMPLETED`, `TASK_STATE_CHANGED`, `BUDGET_EXCEEDED`, `TASK_FAILED` — now including its `reason_code`, `SELF_CORRECTION_TRIGGERED`) already emits an event. `HarnessToolCallORM` is engineering evidence; if Sprint 18 needs "recall the failed validation," it should read the audit table + relevant events, not add a new projection field to the audit table.
- **Extending `harness = "tool_loop"` to another Role** must reuse the same permission intersection and audit path. Add its tool_loop contract to `TEMPLATE.tool_loop_contracts` (keyed by `role.key`), grant its `RoleSpec.tools`, and the engine will pick it up with zero engine edits — provided you preserve `stage_kind == "produce"` (otherwise `resolve_permitted_tools` returns empty).

---

## 18a. Sprint 17 Handover — Self-Correction

### What Sprint 17 achieved

- `agent_harness/orchestrator.py`: termination-interception correction loop bounded by `MAX_CORRECTION_ATTEMPTS = 3`, explicit surrender via a `**Unable to Complete:**` marker, both producing `TASK_FAILED` with an additive `reason_code` payload field (`self_correction_exhausted` / `employee_surrendered`) instead of routing to the Reviewer.
- New seventh tool `revert_last_patch` (zero provider-supplied arguments) in the immutable registry, granted only to `ENGINEER`. `WorkspaceManager.revert_last_commit`/`head_sha` added to the port + `LocalGitWorkspaceManager` impl, ancestry-checked before any reset.
- `LoopState` (mutable, `agent_harness/context.py`) threaded alongside the frozen `ToolRunContext`; `ToolRunContext` gained `branch_base_sha`.
- Three synthetic `HarnessToolCallORM` rows (`_loop:correction_interception`/`_loop:correction_exhausted`/`_loop:employee_surrendered`, `status="recorded"`) — no new table, no migration.
- `get_harness_summary`/`HarnessSummaryResponse` extended with `correction_attempts`, `rollback_count`, `surrendered`, `exhausted`.
- New `SELF_CORRECTION_TRIGGERED` event, published via an injected callback (harness still never imports `EventBus`).
- Two new mock-provider scenarios (`SELF_CORRECTION_DEMO`, `SELF_CORRECTION_ROLLBACK`) plus 17 new/changed backend tests (14 orchestrator correction/rollback tests, 2 registry test updates for the 7-tool set, `test_self_correction_integration.py`, `test_workflow_engine_reason_code.py`).
- Full detail and rationale: `docs/DECISIONS.md` #239–#242.

### What was validated (honestly)

- Full pytest suite: green (472 passed, 6 skipped — baseline 455 + 17 new/changed).
- Dashboard `tsc --noEmit` + `next build`: green, all 19 routes — no dashboard code changed beyond the regenerated TS event contract (`SELF_CORRECTION_TRIGGERED`, additive-only).
- Alembic head unchanged (`b1f4c8d5e9a2`) — no migration.
- Mock E2E with zero provider keys: green (both new scenarios drive a real pipeline run through `PENDING_APPROVAL`).
- Independent 12-item security audit (dedicated read-only agent, not self-audit): all PASS.
- **Browser verification: classified as UNVERIFIED** — Sprint 17 introduced no CEO-facing UI change (§9's hard no-UI decision), so there was nothing new to browser-verify.

### What Sprint 18 should be aware of

- **No cross-run or cross-Mission learning exists yet.** Every attempt starts with `LoopState.correction_attempts == 0`; nothing recalls a prior Mission's failure pattern. This is exactly Sprint 18's Project Memory territory.
- **Rollback is per-patch, not per-attempt.** An Employee walks back one `apply_patch` commit per `revert_last_patch` call, each consuming a budget slot — there is no "reset to Mission start" tool.
- **Surrender detection is regex-based** (`**Unable to Complete:**`, case-insensitive). A provider could theoretically evade it by rewording; impact is bounded because an Employee that neither fixes nor surrenders still exhausts its correction budget and fails anyway.
- **No CEO-facing dashboard surface for correction/rollback stats.** `get_harness_summary`'s new fields are API-only — same reasoning as Sprint 16's un-widgeted summary endpoint.

---

## 18b. Sprint 18 Handover — Project Memory

### What Sprint 18 achieved

- New module `app/modules/memory/` (`registry.py` frozen category tuple + `EventType → category` map + bounded-content/recall constants; `projection.py` pure zero-LLM extractors; `service.py` `record_memory`/`recall`; `subscriber.py` live `EventBus` subscriber wired in `main.py::lifespan`; `backfill.py` idempotent replay; `schemas.py` `MemoryRecord`/`RecallRequest`/`RecalledMemory`).
- New table `memory_records` (migration `c2a7e1f4b6d3`, `down_revision = 'b1f4c8d5e9a2'`), `UNIQUE(source_event_id)` as the sole dedup mechanism.
- Six categories populated from eight existing `EventType`s: `ceo_approvals` (`APPROVAL_GRANTED`/`APPROVAL_REJECTED`/`APPROVAL_CHANGES_REQUESTED`), `pm_specifications` (`SPECIFICATION_APPROVED`), `reviewer_feedback` (`REVIEW_COMPLETED`), `failed_attempts` (`TASK_FAILED`, including Sprint 17's `reason_code`), `successful_solutions` (`TASK_COMPLETED`), `prior_discussions` (`SPECIFICATION_TURN_POSTED`). `architecture_decisions` and `coding_conventions` were scoped out — no event carries them as first-class structured facts yet.
- `PlanningOrchestrator` gained PM-explicit-only recall: `_validate_recall_request_optional` (PM turn kinds) / `_reject_recall_request` (CTO turn kinds, parse-time), `_maybe_recall` (always publishes `MEMORY_RECALLED`, even on zero matches), and a single-turn-lifetime `pending_recall_message` local threading the ranked results into the *next* turn only.
- New event `MEMORY_RECALLED` (`spec_id`, `requested_categories`, `match_count`, `memory_ids`).
- One-shot operator action `scripts/backfill_memory.py [--project-id ID]` for Companies whose event history predates the subscriber.
- New `RECALL_DEMO_MARKER` mock-provider fixture scenario exercising the real recall path end-to-end.
- No new HTTP route, no new dashboard surface (§8/§12 out of scope by design).
- Full detail and rationale: `docs/DECISIONS.md` #243–#247.

### What was validated (honestly)

- Full pytest suite: green (512 passed, 6 skipped — baseline 472 + 40 new/changed).
- Dashboard `tsc --noEmit` + `next build`: green — no dashboard code changed; the only dashboard-adjacent change was a stale-drift fix to the regenerated `MemoryRecalledPayload` TS type (zero dashboard references to the corrected fields, confirmed via grep).
- Migration round-trip (`upgrade head` → `downgrade -1` → `upgrade head`) verified against a throwaway Postgres database, not the real dev DB.
- Mock E2E with zero provider keys: green, including a real `MockProvider.complete`-driven recall scenario (`RECALL_DEMO_MARKER`).
- Independent 12-item security audit (dedicated read-only `Explore` agent, not self-audit): all PASS.
- Scope-leakage diff review (`git diff --stat` against the true pre-Sprint-18 baseline, not a stray intermediate commit): zero dashboard changes, zero new HTTP routes.
- **Browser verification: classified as UNVERIFIED** — Sprint 18 introduced no CEO-facing UI change (§8's explicit no-UI scope), so there was nothing new to browser-verify.

### What Sprint 19 should be aware of

- **Memory has no CEO-facing surface yet.** Recall results are visible only inside the PM↔CTO planning transcript (as an injected message) and on the Timeline (as `MEMORY_RECALLED`). A dedicated widget or Sidebar page reading `memory_records` directly is a natural, currently-unclaimed Sprint 19+ candidate — but must go through a route, not a direct table read from the dashboard (Rule #1).
- **Recall relevance is naive keyword/tag/category matching plus recency decay** (`1/(1+age_days/30)`) — no stemming, no vector search, no cross-Company memory. If a future sprint wants smarter recall, that's a scoped decision, not an incremental tweak to `service.recall`.
- **`architecture_decisions` and `coding_conventions` are not in `registry.CATEGORIES` at all** — `docs/ARCHITECTURE.md` §5's original sketch named eight categories, but only six shipped because no current event carries the other two as structured facts. Adding either requires a new event/extractor pair and a `CATEGORIES` tuple change, not just a registry entry.

---

## 18d. Sprint 19 Handover — V1.1 Shipping: Verification, Observability, Release

### What Sprint 19 achieved

- **`OpenRouterProvider`** (`provider_gateway/openrouter_provider.py`, new) — a third first-party `ProviderGateway`, built from scratch rather than an `AnthropicProvider` subclass (OpenRouter always speaks the OpenAI wire format regardless of upstream model — DECISIONS.md #249). `COMMANDER_PROVIDER` now accepts `mock | anthropic | openrouter`; existing three-tier model resolution (Employee → CEO per-role → registry default) works uniformly across all three.
- **Structured JSON logging** (`core/logging.py`, new) — one `JSONFormatter`, per-request `request_id` (server-issued UUID via `CorrelationIdMiddleware`, never trusts a client header) and per-Mission `task_id`/`agent_id`/`project_id` contextvars set at `workflow_engine.py`'s `_spawn`/`_run_role`/`_run_engineer_tool_loop` boundaries. No new logging dependency.
- **`scripts/load_smoke.py`** (new) — 4 scenarios (10 sequential Missions in 1 Company; 3 Companies × 3 concurrent Missions each with live SSE; hot-path query counts; Memory recall at 1,000 records) forming the documented operating envelope in `docs/KNOWN_ISSUES.md` §6. Building scenario 2 surfaced and fixed two real concurrent-Mission races: `DBAgentRuntime._claim_agent` (a bounded poll/retry wrapper around the `IDLE→ASSIGNED` transition, so a busy single-Employee-per-Role founding roster is waited out rather than crashing) and `AgentRuntime.transition()` rewritten as an atomic compare-and-swap `UPDATE ... WHERE state=:current` instead of a non-atomic read-then-write. Full detail: DECISIONS.md #250.
- **`docs/DEPLOYMENT.md` + `.env.production.example`** (new) — first-deployment walkthrough, production run recipe (systemd/nohup, `--workers 1` deliberate), optional nginx TLS example, `pg_dump`/`tar` backup-restore, and the v1.0.0→v1.1 upgrade path (Sprint 9 auth schema migration + manual `owner_id` attribution, since no migration can know the correct CEO for pre-auth data). Dry-run walkthrough and an Alembic `downgrade -1` → `upgrade head` round trip both verified clean against this repo's real Postgres 16 container.
- **`docs/KNOWN_ISSUES.md`** (new) — every CLAUDE.md §15 accepted tradeoff, every Sprint 15–18 deferral, the load-smoke operating envelope, provider-variance notes (free-tier reliability varies; Rule #18 held under real `429`/`402` failures), and the v1.0→v1.1 upgrade caveats, consolidated in one place.
- **`CHANGELOG.md`** (new) — the v1.1.0 feature summary across Sprints 9–19, including the two breaking changes (Sprint 9 auth schema, Sprint 10 `role_key` rename).
- **Independent security audit** (dedicated agent, not self-audit) against sprint-19.md §2's 7 security requirements. 6/7 passed outright; 1 real finding, fixed same-sprint — see DECISIONS.md #251.

### What was validated (honestly)

- Full pytest suite: green, 553 passed / 6 skipped (re-verified twice — once after the concurrent-Mission-race fixes, once after the security-audit logging fix — zero regressions either time).
- Dashboard `tsc --noEmit` + `next build`: both green, all routes compiled.
- `scripts/load_smoke.py`: all 4 scenarios PASS, stable across repeated runs.
- Alembic round trip (`downgrade -1` → `upgrade head`) verified against this repo's real Postgres 16 container, not just SQLite.
- Real-LLM E2E: the free-tier OpenRouter smoke test (`openai/gpt-oss-20b:free`) was run several times — provider wiring confirmed working; free-tier reliability confirmed to vary (malformed tool-call JSON, occasional `clarification_required`, reproduced `429` rate limiting); Rule #18 held under every real failure observed.
- **Both paid release-evidence runs (Anthropic direct, Claude-via-OpenRouter) are UNVERIFIED IN THIS ENVIRONMENT** — no `ANTHROPIC_API_KEY` configured, and the configured `OPENROUTER_API_KEY` account has no funded credits (confirmed via a real `402 Payment Required`). Recorded honestly in `docs/KNOWN_ISSUES.md` §7 rather than faked (CLAUDE.md §16.7). **This is the one concrete gap the next operator/CTO should close** — supply a funded key for either or both providers and re-run `make verify-llm` / `make verify-llm-openrouter --model anthropic/claude-sonnet-4.5` before treating those specific claims as verified.
- Browser/UI verification: Sprint 19 introduced no new CEO-facing UI (§4.10's explicit no-new-UI scope) — nothing new to browser-verify from this sprint's own changes. The CEO's own hands-on verification of the whole app (existing UI, this sprint's backend changes underneath it) is the standing gate before any `v1.1.0` tag — see below.

### What the next CTO/operator should be aware of

- **The `v1.1.0` git tag was deliberately NOT created this sprint.** Per explicit standing instruction from the CEO, Sprint 19's own completion is committed and pushed, but the release tag itself is the CEO's personal call after hands-on browser verification. Do not assume `v1.1.0` exists just because Sprint 19's checklist is complete — check `git tag` directly.
- **The two release-evidence gaps above are credentials-only, not code gaps.** Both provider code paths are exercised end-to-end by the free-tier OpenRouter smoke test (same script, same `OpenRouterProvider` code path, different model/account funding). Closing the gap is an operator action (fund a key), not an engineering task.
- **`httpx.ASGITransport`'s SSE limitation is a permanent testing-technique constraint, not a bug to watch for regressing.** Any future test that opens a `client.stream(...)` SSE connection against the app via `ASGITransport` will hang unconditionally, regardless of app code — use a real `uvicorn.Server` on loopback instead, per `scripts/load_smoke.py` scenario 2's pattern.

---

## 19. CTO Warnings

### Things I would tell the next CTO personally

**Do not bypass `dispatch_tool_call`.** It is deliberately the single entry point (schema→auth→run→bound→audit). Handlers are not intended to be called directly outside tests. If you skip dispatch, you skip the audit row and the authorization; that's not "faster," it's a security regression.

**`_run_pipeline` is 300 lines and looks refactor-able. Resist.** Its shape mirrors the exact document/code branching + resume-from-index + orphan-safe session pattern that took Sprint 9+16 iterations to get right. Every session is opened fresh for a reason (Rule #9.3). Every `dataclasses.replace(task, ...)` after a mutation is intentional. Every explicit `except BudgetExceededError` before the generic `except Exception` is intentional. If you refactor, keep the shape.

**`_release_agent_to_idle` walks two state edges deliberately.** `AGENT_TRANSITIONS` has no direct WORKING→IDLE edge — the walk-back must be **two transitions** (WORKING→FAILED→IDLE or WAITING_REVIEW→COMPLETED→IDLE). Trying to "just set state = idle" is exactly the bug Sprint 9 orphan recovery found — it left agents parked in busy states so the *next* mission's InvalidTransition crashed the pipeline.

**`apply_patch` commits immediately. Yes, immediately.** DECISIONS.md #234 explains the whole reason. Every read tool resolves through a committed ref via `git show ref:path`. If you defer the commit, you break the Engineer's ability to observe its own writes in the same loop.

**The `ValueError` swallow in `apply_patch` looks wrong. It isn't.** `write_files` reports a path as "written" whenever it wrote bytes, even if identical to committed content. `commit()` then raises `ValueError("commit() called with nothing staged")`. This is the only source of `ValueError` in `local_git.py`, so the narrow `except` cannot mask an unrelated failure. Do not "widen" or "narrow" it without re-checking DECISIONS.md #236.

**Do not add per-tool-call `EventBus.publish` calls.** The audit-vs-events split is deliberate. `HarnessToolCallORM` is engineering evidence; the Timeline is CEO narrative. If you want CEO visibility on individual tool calls, add a bounded aggregate route (like `harness-summary`) — do not stream a hundred events per Mission.

**`_run_engineer_tool_loop` creates the workspace/branch BEFORE the loop.** The one-shot path lands after. Do not mirror them. Every tool call resolves against a committed branch, so the branch must exist.

**Do not read `ANTHROPIC_API_KEY` from `settings.` directly.** Even in tests. Go through `SecretsProvider`. The Company Settings runtime override depends on this being the single choke point.

**Rule #16's guard is real.** `test_role_hardcoding_guard.py` walks the AST. `if role == "engineer":` will fail CI. Comments don't help. Route it through `RoleSpec` or `StageSpec` data.

**Do not read from a `TaskORM` after `await`ing on a provider.** `TaskSnapshot` exists for a reason. `dataclasses.replace(task, branch_name=...)` after a mutation is not decorative — it is the mechanism that keeps the snapshot in sync with the DB across sessions.

**Rule #11 is architectural, not UI.** There is no `POST /api/agents/{engineer_id}/message` route. Adding one — even "just for debugging" — is a Rule #11 violation. Debug via the Timeline and the audit table.

**The mock provider is a fixture, not a behavioral model.** `_tool_loop_response` is keyed off `len(messages)` and does 5 turns in a fixed sequence. Do not reason about real Anthropic behavior from its branch structure. `_is_rework()` checks for a marker string — that's a test-fixture correction (DECISIONS.md #236), not product behavior.

**Cancellation is BaseException, not Exception.** `asyncio.CancelledError` is `BaseException`. The `except (ToolDeniedError, ...)` clauses in `orchestrator.py` do not catch it by design. If you refactor an `except:` bare clause anywhere, keep this straight — swallowing `CancelledError` will make cancel silently fail.

**`_check_budget` re-runs before every stage.** Not once. Not at start. Every stage. The `_block_task_on_budget` path requires the task to be in a state BLOCKED is reachable from — which is why the exception is raised in `_check_budget` and blocked in the pipeline handler, not blocked inline.

**404 not 403.** For everything. Rule #15. If you write a route that returns 403 for cross-account, you're leaking existence.

**The founding singleton lock trap (DECISIONS.md #183).** `create_department` inserts `RoleSingletonLockORM` rows in the same transaction as the founding singleton Employees. If you touch the founding path, keep this invariant — otherwise the *first* post-founding hire for the founding singleton slips through and creates a duplicate.

**Alembic head is authoritative.** Do not `Base.metadata.create_all()` outside tests. The current head is `b1f4c8d5e9a2_harness_tool_calls`. If you add a migration, verify upgrade + downgrade round-trip against real Postgres (`scripts/seed.py` is the reference).

**When you're tempted to "just add a tool"**: read `docs/prompts/sprint-16.md` §4.1–§4.13. The registry is code-owned and immutable. A new tool needs a schema, a permission story, a handler, an audit summary rule, and tests. There is no configurable-tool path — that would be Rule #12 violation.

**Do not make correction interception fire on validation failure itself.** It fires on a *blocked termination attempt* while `last_validation_status == "failed"`. An Employee that proactively fixes its own failure without ever trying to stop must never be intercepted and must never spend a correction attempt — that's the entire point of §4.16's decision table (DECISIONS.md #240). If you "simplify" this to fire eagerly, you'll silently break the `SELF_CORRECTION_DEMO` mock scenario's core assertion (`correction_attempts == 0`, no `agent.self_correction_triggered` event) and penalize well-behaved Employees.

**`revert_last_patch`'s target sha is never provider input — keep it that way.** The schema (`RevertLastPatchArgs`) has zero fields on purpose. If you're ever tempted to add a "revert to specific commit" argument, that's a different, much riskier tool — it would let the provider choose an arbitrary rollback point instead of the server-computed one, reopening exactly the kind of untrusted-input risk Rule #9/#12 exist to close.

**Do not skip `revert_last_commit`'s ancestry check "for efficiency."** `git merge-base --is-ancestor` runs before every `git reset --hard` in the rollback path. It is the only thing standing between "denied" and "destructive" if `branch_base_sha` or the commit history is ever wrong. It fails closed (`WorkspaceConflictError` → `ToolDeniedError`) — do not turn that into a bypassable warning.

**`MAX_CORRECTION_ATTEMPTS` is a loop-shape constant, not a settings knob — on purpose.** It lives next to `MAX_DENIED_STREAK`/`MAX_MALFORMED_STREAK` in `orchestrator.py`, not in `config.py`. If a future sprint wants it operator-tunable, that's a deliberate scope decision to make explicitly, not a "just move the constant" refactor — see DECISIONS.md #240.

**Surrender and exhaustion both bypass the Reviewer, deliberately.** `_run_engineer_tool_loop`'s exception handling routes `SelfCorrectionExhaustedError`/`EmployeeSurrenderedError` straight to `_fail_task_with_reason_code`, never through `_land_tool_loop_changes`. Don't "helpfully" let the Reviewer see a Mission that never passed its own validation — that would defeat the entire self-correction contract.

**Do not let `recall()` or any `memory/projection.py` extractor call `ProviderGateway`.** Both are load-bearing on being deterministic and cheaply testable with plain assertions. If a future sprint wants LLM-scored relevance, that is a new, explicitly-scoped surface — not a quiet upgrade to the existing pure functions.

**Do not make recall implicit.** `_maybe_recall` must keep firing only when the just-persisted PM turn's JSON actually carried a non-null `recall_request`. Injecting memory into every PM turn "for better context" breaks the fixed, budgeted-cost framing `MAX_RECALL_*` depends on (Rule #13) and was explicitly rejected — see DECISIONS.md #245.

**`memory_records`'s dedup is the DB constraint, not application logic.** `UNIQUE(source_event_id)` is what makes both the live subscriber and `backfill_memory` safe to run against the same event twice. Don't add an in-code "already exists?" check in front of it — that would just be a second, potentially-inconsistent source of the same guarantee.

**`recall()` must keep scoping to the calling Company's `project_id`.** There is no cross-Company memory by design (Rule #15's account-scoping logic extends here even though Memory itself isn't a `users`-owned table). If you ever see a recall path that takes a bare `category`/`keyword` filter without a `project_id`, that's a scoping regression, not a feature.

**Do not read `settings.openrouter_api_key` (or any provider key) from anywhere outside `secrets.py`.** `OpenRouterProvider` goes through `SecretsProvider` exactly like `AnthropicProvider` does — that's what makes it a real proof of Rule #4, not a special case. A shortcut read anywhere else (a route handler, a log line, a debug print) is a Rule #7 violation waiting to happen, not a harmless convenience.

**Do not revert the log formatter's secret-key redaction back to exact-match.** `apps/api/app/core/logging.py`'s `_SECRET_KEY_TERMS` check is deliberately a substring match, not `key.lower() in _SECRET_KEYS`. The exact-match version was the Phase 2 design and it was wrong — the Sprint 19 independent security audit showed it would let real field names like `api_key`, `auth_token`, `password_hash` through in the clear. See DECISIONS.md #251 for why this supersedes the earlier decision. If you're adding a new secret-shaped field name, extend `_SECRET_KEY_TERMS`; don't narrow the match style.

**Any future test that opens a concurrent SSE connection through `httpx.ASGITransport` will hang unconditionally — this is not a regression to chase.** `ASGITransport` buffers the entire ASGI response before returning, which is structurally incompatible with a never-terminating SSE stream. `scripts/load_smoke.py` scenario 2 works around this by running a real `uvicorn.Server` on loopback instead. Don't spend time debugging a hung `ASGITransport`-based SSE test — switch the test to a real server.

**Do not create or push the `v1.1.0` git tag.** That decision belongs to the CEO alone, made after hands-on browser verification — see DECISIONS.md's Sprint 19 close-out entry. Sprint 19 being "done" in `PROGRESS.txt`/git history is not the same claim as "V1.1 is released," and the two must not be conflated in any commit, tag, or status line.

---

## 20. How To Safely Work On Commander

### 20.1 Before starting any work

1. `git status`, `git log --oneline -10`, and check `PROGRESS.txt` for the current sprint's status.
2. Read `CLAUDE.md` end-to-end (once) and the current sprint brief in `docs/prompts/` (fully).
3. Skim `docs/DECISIONS.md` for the last 20 entries — they'll usually explain 80% of "why does this look weird?"
4. `make test` on a fresh clone to establish baseline (`455 passed / 6 skipped` at Sprint 16 close).
5. `make dev` and click through the app once. The dashboard is the ground truth for CEO-facing behavior.

### 20.2 Before touching a subsystem

- **Any harness change:** read all of `apps/api/app/modules/agent_harness/` first. Then read DECISIONS.md #233–#238. Then look at `test_agent_harness_*.py`.
- **Any workflow change:** read `apps/api/app/modules/workflow_engine/engine.py` from top to bottom. Then `test_code_missions.py` and `test_reliability.py`.
- **Any role/employee change:** read `apps/api/app/templates/software_company.py` and `test_role_hardcoding_guard.py`. Run the guard.
- **Any migration:** read `apps/api/alembic/versions/*` and verify round-trip against real Postgres (`docker compose up`), not sqlite.
- **Any secret handling:** read `core/secrets.py`, then grep for `settings.anthropic_api_key` — should have exactly one legitimate reader.
- **Any auth change:** read `modules/auth/service.py` and `core/ownership.py`. Every new route should use `Depends(get_current_user)` and `project_owned_by`/`resource_owned_by`.

### 20.3 Before shipping

1. `make test` green (backend + dashboard typecheck + build).
2. Alembic upgrade round-trip works if you added a migration.
3. Mock mode still works with zero keys — try `COMMANDER_PROVIDER=mock` explicitly.
4. If CEO-facing UI changed, actually click through it in a browser. Don't claim browser-verified from tests.
5. Update `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, and (if CEO-facing) `docs/design/UX_SPEC.md` **in the same commit**. Rule #10.
6. Update `PROGRESS.txt` per completed item — do not batch at the end.
7. Push. Verify `remote HEAD == intended final commit`. Sprint is not complete until this holds.

### 20.4 If something surprising happens

- **A pipeline stage silently stops:** check `_check_budget`, cancellation, or a swallowed exception in an `except`. `_run_pipeline`'s explicit `except (CancelledError, BudgetExceededError, Exception)` fan-out is the shape it must keep.
- **A route returns 500:** `main.py`'s unhandled exception handler adds CORS headers manually (DECISIONS.md — Sprint 10) so a real crash doesn't look like a CORS bug. Check server logs for the actual traceback.
- **A test that was green fails after a template edit:** you probably relied on stock template data being inert. Add explicit fixtures (`UNGRANTED_ROLE`/`EMPTY_TEMPLATE` pattern) rather than depending on stock data (DECISIONS.md #235).
- **`InvalidTransition` at runtime:** you set state directly instead of going through `transition()`. Always go through the state machine.
- **Sqlite tests pass but Postgres fails:** almost always a naive/aware datetime issue, or a missing `use_alter` on an FK cycle, or a nullable column that Postgres treats differently. Grep for the pattern.
- **Provider says one thing, code says another:** provider output is untrusted. Schema-validate it. Never branch on provider-specific formatting (Reviewer verdict is the exception, and it's the ONE hard contract).
- **A tool call is being denied when you think it shouldn't be:** re-derive `resolve_permitted_tools(...)` manually with the actual values. Any missing term is denial. Check `stage_kind == "produce"`, `workspace_ready`, `RoleSpec.tools`, `SkillTemplate.capabilities`, and `harness_enabled`. Fail-closed is a feature.

### 20.5 Anti-patterns to avoid

- Creating a new event-like table for a domain that already has events. Rule #14.
- Adding a `if role_key == "..."` anywhere outside `app/templates/`. Rule #16.
- Widening a narrow `except`. The narrowness usually encodes a known invariant.
- Adding a `run_shell` or generic command tool. Rule #12. Permanent.
- Storing tool definitions or executables in the DB. Rule #12.
- Deferring `apply_patch`'s commit. DECISIONS.md #234. Every read tool resolves through a committed ref.
- Emitting a per-tool-call Timeline event. Use the audit table.
- Returning 403 for cross-account. Rule #15.
- Skipping `SecretsProvider` for a "quick test."
- Adding a CEO→Engineer/CTO/Reviewer conversation route. Rule #11.
- Assuming mock mode is a degraded developer-only feature. Rule #6. It is a first-class product feature.

---

**End of handover.**

If this document ever contradicts the code, the code wins. Update this document in the same commit as the change that made it contradict — Rule #10 applies to CTO handover notes too.
