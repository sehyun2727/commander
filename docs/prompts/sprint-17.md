# Sprint 17 — Self-Correction Loop

Execute this sprint autonomously from Phase 0 through Phase 4.

Expected baseline:
- local HEAD: 9cfedc9
- origin/master: 9cfedc9
- backend baseline: 455 passed / 6 skipped
  (2 of the 6 skips are Windows symlink-privilege skips in
  `test_agent_harness_guards.py` — expected on Windows dev, absent on Linux)
- dashboard typecheck/build: PASS (19 routes compile)
- migration head: `b1f4c8d5e9a2_harness_tool_calls`
- mock E2E with zero provider keys: PASS
- browser-rendered interaction verification: UNVERIFIED (Sprint 16 introduced no CEO-facing UI)

Repository and git state are authoritative. Verify every baseline claim first.

Follow the current CLAUDE.md, architecture, decisions, UX specification, security constraints, progress discipline, verification standards, and reporting format.

Do not stop for routine confirmation. Stop only for a hard blocker, destructive ambiguity, security/cost exposure, or irreconcilable architectural conflict.

---

## 1. Goal

Give the Agent Harness's Engineer the ability to **detect its own validation failures, react to them inside its budget, correct them via patches, and tactically roll back its own bad edits — all bounded and observable — without ever dumping a silently-broken deliverable on the Reviewer.**

At the end of Sprint 17:

1. `run_validation` outcomes are structured signals the orchestrator tracks, not just text the Employee reads.
2. An Engineer that tries to finish while its most recent validation failed is intercepted, reminded, and required to either fix the failure or explicitly surrender.
3. Self-correction is bounded by an explicit correction-attempt limit alongside the existing tool-call and wall-time budgets.
4. The Engineer can tactically undo its most recent `apply_patch` via a new `revert_last_patch` tool, without ever escaping the mission branch's base commit.
5. Rollback never crosses the branch base and never touches commits it did not itself create in this tool loop.
6. Explicit Engineer surrender is a first-class outcome distinct from crash or budget exhaustion.
7. Self-correction exhaustion is a structured Mission failure with a diagnostic reason and preserved evidence.
8. The Timeline shows a single, coarse "the Engineer entered self-correction" beat — not per-call noise (audit-vs-events split, DECISIONS.md #233/#237).
9. Cancellation, budgets, permission intersection, secrets handling, sandbox isolation, and audit persistence from Sprint 16 remain intact.
10. Mock mode deterministically exercises correction success, rollback success, and correction exhaustion with zero provider keys.
11. Reviewer receives the same diff + change summary + check summary evidence it always did, from a corrected (or explicitly-failed) deliverable rather than a silently-broken one.
12. Existing planning, specification, mission, workspace, and widget behavior remains functional.

This sprint builds the loop-level self-correction and tactical rollback the harness deliberately deferred in Sprint 16 (DECISIONS.md #238).

It does not implement cross-attempt learning, organizational memory, review-driven auto-fix, escalation policies, autonomous rollback across runs, unrestricted git operations, arbitrary shell, new roles, provider expansion, or a CEO Workspace redesign.

---

## 2. Security Model

Sprint 16's security model (`docs/prompts/sprint-16.md` §2) applies unchanged. Treat everything the provider produces — including any surrender text, any correction reasoning, any `revert_last_patch` argument shape — as untrusted.

Sprint 17 adds one new mutating tool (`revert_last_patch`), one new mutating `WorkspaceManager` method (`revert_last_commit`), and one new orchestrator control path (correction interception). Each must satisfy:

- Server-owned, code-only definition. No client/DB/RoleSpec/provider input can invent a new tool key, extend the branch base, or bypass correction bounds.
- Fail-closed authorization via the existing intersection (§4.9 below).
- Confinement: rollback operates only on commits recorded during this tool loop, only within the mission branch, and never past `branch_base_sha`.
- Bounded: correction attempts are capped; rollback consumes tool-call budget like any other call.
- Observable and auditable: every corrective retry, rollback, and surrender is persisted (audit table + one Timeline beat).
- Cancellation-safe: `asyncio.CancelledError` still propagates uncaught.

The Employee gains more agency; it does not gain more surface. There is still no shell, no arbitrary command, no arbitrary git operation, no network, no cross-branch touch, and no path outside the workspace.

---

## 3. Required Repository Inspection

Before changing code, inspect at minimum:

- CLAUDE.md — Rules #9, #12, #13, #16, #18 apply directly
- PROGRESS.txt (currently "SPRINT 16 DONE. Now working on: nothing -- awaiting Sprint 17 brief")
- README.md
- FOR_CTO.md — the current CTO handover, especially §7 (Agent Runtime Architecture) and §19 (CTO Warnings)
- docs/ARCHITECTURE.md, especially §4.5 (as-built harness) and §4.6 (self-correction target)
- docs/DECISIONS.md #233–#238 (Sprint 16 as-shipped)
- docs/design/UX_SPEC.md
- git history through 9cfedc9
- `apps/api/app/modules/agent_harness/` — all 11 files
- `apps/api/app/modules/agent_harness/orchestrator.py::run_tool_loop` — the loop termination path is where correction interception lives
- `apps/api/app/modules/agent_harness/handlers.py` — `dispatch_tool_call`, `apply_patch`, `run_validation`
- `apps/api/app/modules/agent_harness/registry.py` — extending WRITE_TOOL_KEYS and TOOLS
- `apps/api/app/modules/agent_harness/schemas.py` — argument-schema pattern
- `apps/api/app/modules/agent_harness/context.py` — `ToolRunContext` (what's server-issued vs mutable)
- `apps/api/app/modules/agent_harness/budget.py` — bound reuse vs new dimension
- `apps/api/app/modules/workflow_engine/engine.py::_run_engineer_tool_loop` and `_land_tool_loop_changes` — how the loop plugs into the pipeline
- `apps/api/app/modules/workflow_engine/engine.py::_fail_task` and `_block_task_on_budget` — how failures reach the CEO today
- `apps/api/app/modules/workspace_manager/local_git.py` — existing git operations, especially `write_files`, `commit`, `diff`, `diff_stats`
- `apps/api/app/modules/workspace_manager/git_process.py` — how to run git safely
- `apps/api/app/core/interfaces/workspace_manager.py` — port extension shape
- `apps/api/app/core/errors.py` — CommanderError subclass convention
- `apps/api/app/core/events/types.py` — event families and naming
- `apps/api/app/core/db_models.py::HarnessToolCallORM` — audit shape (arguments_summary rules, `status` values)
- `apps/api/app/modules/tasks/service.py::get_harness_summary` — aggregate to extend
- `apps/api/app/modules/provider_gateway/mock_provider.py::_tool_loop_response` — mock fixture pattern
- `apps/api/app/templates/software_company.py::_ENGINEER_CONTRACT_TOOL_LOOP` and `TOOL_LOOP_CONTRACTS` — Engineer's system prompt
- `apps/api/tests/test_agent_harness_orchestrator.py` — the FakeGateway test pattern
- `apps/api/tests/test_agent_harness_handlers.py` — handler test pattern
- `apps/api/tests/test_role_hardcoding_guard.py` — Rule #16 enforcement
- `apps/api/tests/test_code_missions.py` and `test_reliability.py` — end-to-end pipeline tests that already exercise the tool-loop path

Search specifically for:

- every existing termination path of `run_tool_loop`
- every existing raise site of `ToolLoopExhaustedError` / `BudgetExceededError` / `PatchConflictError`
- every existing use of `git reset` / `git revert` (there should be none in `apps/api/app/`)
- every existing use of `HEAD~` (there should be none)
- every existing consumer of `TASK_FAILED.payload` — check whether adding a `reason_code` field breaks any parser (frontend or backend)
- every subscriber to Timeline event types — check whether adding one new event type is a no-op for existing consumers

Document existing execution paths before wrapping or extending them.

---

## 4. Approved Decisions

### 4.1 Scope — validation-failure driven only

Self-correction fires **only** when a `run_validation` tool call has returned `status="failed"` more recently than any subsequent `run_validation` call has returned `status="passed"`.

- `could_not_run` is **NOT** a failure. Sprint 6/16 policy is unchanged: sandbox unavailability degrades to a plain result, never a hard fail, and never triggers correction (otherwise a missing Docker Desktop would force the Engineer into a pointless loop).
- `PatchConflictError`, malformed arguments, and `ToolDeniedError` are already handled by Sprint 16's `denied_streak`/`malformed_streak` counters and are unchanged. Correction is orthogonal to those.
- Reviewer `changes_requested` remains the CEO decision path (`resume_after_decision` → `_REWORK_STAGE_INDEX`). Self-correction lives strictly **inside one produce-stage attempt**. Cross-attempt fixes are Sprint 18 territory.

### 4.2 Correction trigger point

Correction is triggered exactly when the provider returns a completion with **no tool calls** while `last_validation_status == "failed"`.

- The provider is free to call `run_validation` at any point, including as a probe with no intent to terminate; forcing correction after every failed validation would remove Employee agency.
- The interception point is termination. A termination attempt while the last validation failed is not a termination — it is the start of a correction cycle.
- If the Employee never calls `run_validation` at all, the loop terminates normally (unchanged Sprint 16 behavior). Do not retrofit "must validate before finishing" as an engine-level rule; that stays in the Employee's contract text.

### 4.3 Correction budget

Introduce a new constant in `agent_harness/orchestrator.py`:

```
MAX_CORRECTION_ATTEMPTS = 3
```

- One correction attempt = one intercepted termination-with-failed-validation.
- Between attempts, the Employee may make any legal tool calls (typically read → patch → revalidate → possibly rollback).
- Each attempt still consumes tool-call budget (`HarnessBudget.max_tool_calls`) and wall-time budget (`HarnessBudget.max_seconds`) as its individual tool calls run — correction adds a bound, does not replace the existing bounds.
- Exhaustion (attempts consumed AND last validation still failed at final termination attempt) raises a new `SelfCorrectionExhaustedError`.

Rule #13 (bounded loops): the loop cannot correct forever. Two other bounds already apply (per-attempt tool-call budget, wall-time budget); this one bounds specifically "how many times the loop will refuse to accept a failed termination."

### 4.4 Corrective reminder — server-owned text

When correction is triggered, the orchestrator appends one **server-issued** user message to the conversation before continuing the loop. The message text is a code-level constant, not provider-supplied and not derived from provider output. It states:

- The most recent validation failed.
- The Employee must either fix and re-run validation, or explicitly surrender (see §4.5).
- How many correction attempts remain.

Keep it short, deterministic, and free of any secret-shaped content. Never echo the raw validation output back in this message; the Employee already has it from the previous `run_validation` tool_result block.

### 4.5 Explicit surrender

Give the Employee a clean exit even when the last validation failed. If a termination attempt's final text contains the marker `**Unable to Complete:**` (case-insensitive, matched with the same lenient regex convention `parse_verdict` uses):

- The orchestrator accepts the termination immediately, regardless of `last_validation_status`.
- The result carries `stop_reason = "employee_surrendered"`.
- `_run_engineer_tool_loop` treats this as a Mission failure (see §4.10) with the Employee's stated explanation as the diagnostic.

Rationale: an Employee that has honestly concluded it cannot resolve a failure must be able to say so — Rule #18 ("CEO actions never fail silently") applies symmetrically to Employee actions. Better an explicit, reasoned failure than a bounded loop grinding until exhaustion.

The marker is a workflow-semantic string, mirroring how `parse_verdict` reads `**Verdict:**` and how the code contract uses `**Change Summary:**`. It is not a role-identity branch; Rule #16 is unaffected.

### 4.6 Rollback — `revert_last_patch` tool

Add one new tool to the registry:

```
revert_last_patch  (mutates=True, requires_capability="repository_tools")
```

- Zero arguments (Pydantic model with `extra="forbid"` and no fields).
- Semantics: reverts the mission branch to the commit that existed **immediately before the most recent `apply_patch` commit made during this tool loop**.
- Backed by a new `WorkspaceManager.revert_last_commit(project_id, branch_name, target_sha)` port method.
- Implementation in `LocalGitWorkspaceManager`: `git checkout branch && git reset --hard <target_sha>`. This is destructive to unpushed local state; it is safe here because the mission branch is a private per-Mission branch never shared, and `target_sha` is a value only the harness can produce (see §4.7).

### 4.7 Rollback bounds — hard checklist

`revert_last_patch` must NOT become a generic `git reset` primitive. It has one and only one shape: **undo exactly one commit that this same tool loop just produced via `apply_patch`, on this same mission branch, without ever crossing the branch's base.** Every one of the following must hold:

1. **Zero arguments from the provider.** The tool's Pydantic schema has no fields. The provider cannot supply a target SHA, a commit reference, a number-of-commits, a branch name, or anything else. The target is computed server-side from orchestrator-local state.
2. **Current mission branch only.** The tool operates on `ToolRunContext.branch_name`. It never touches `main` or any other branch. The `WorkspaceManager.revert_last_commit` implementation must checkout `branch_name` explicitly, not "the current branch," so a stray git state cannot cause it to reset the wrong branch.
3. **Never past `branch_base_sha`.** `branch_base_sha` is recorded once at loop start and never mutated. The target SHA must be either `branch_base_sha` (reverting the only patch) or an entry earlier in `apply_patch_commit_history`. Any other resolution → `ToolDeniedError`.
4. **Only real commits this loop produced.** The orchestrator maintains `apply_patch_commit_history: list[str]` — SHAs of commits produced by successful, non-no-op `apply_patch` calls during this same loop (see §4.8 for the byte-identical no-op exclusion). The target is `apply_patch_commit_history[-2]` if `len ≥ 2` else `branch_base_sha`. Never pulled from `git log`, never inferred from the tree state.
5. **Ancestry verified before reset.** Before `git reset --hard <target>` runs, verify with a bounded git command (`git merge-base --is-ancestor <target> <current-head>` or equivalent) that the target is actually reachable from the current branch HEAD. If the check fails (unexpected divergent state) → `ToolDeniedError`, no reset.
6. **`shell=False`, argv-list only.** `WorkspaceManager.revert_last_commit` uses the same `git_process.git(...)` argv-list convention every other git call in this codebase uses. No shell string, no interpolation, no `git reset -- $VAR`. Follows Sprint 16 audit §5.9.
7. **Empty history denies immediately.** If `apply_patch_commit_history` is empty at dispatch time → `ToolDeniedError("no patch to revert")` before any git command runs.
8. **Consumes one tool-call budget slot.** `context.budget.record_tool_call()` fires before dispatch, exactly like every other tool.
9. **Post-success bookkeeping (orchestrator-side, not handler-side):**
   - Pop the last entry from `apply_patch_commit_history`.
   - Clear `last_validation_status` (post-rollback the branch state differs; the Employee should re-validate before terminating — see §4.16).
   - Return a short confirmation to the Employee (e.g. `"reverted 1 patch; branch now at <short-sha>"`).
10. **Failure mode is `ToolDeniedError` or `ToolCallMalformedError`, never a partial-state exception that leaves the loop in an unknown branch state.** If the git command itself fails after passing the ancestry check (extremely unlikely — e.g. filesystem error), raise a plain exception; the pipeline handler's generic `except` translates it to `TASK_FAILED`. Do not attempt a recovery reset.

### 4.8 Rollback of byte-identical patches

Sprint 16 DECISIONS.md #236 documented that a byte-identical `apply_patch` produces no new commit (the `commit()` `ValueError` is swallowed as a benign no-op). Consequences:

- `apply_patch_commit_history` must be appended to only when `apply_patch` produces a **real** commit, not on the no-op path. Detect via the pre/post branch HEAD sha, not via the handler's return string.
- A `revert_last_patch` after a byte-identical no-op patch reverts the last **real** patch before that — which is the correct semantics (the no-op didn't change state, so there is nothing to undo for it).

### 4.9 Permission intersection — unchanged shape

`revert_last_patch` participates in the existing fail-closed intersection (`agent_harness/permissions.py::resolve_permitted_tools`):

```
harness_enabled ∩ RoleSpec.tools ∩ SkillTemplate.capabilities ∩ (stage_kind == "produce") ∩ workspace_ready
```

- Add `"revert_last_patch"` to `ENGINEER.tools` in `app/templates/software_company.py`.
- Add `"revert_last_patch"` to `WRITE_TOOL_KEYS` in `agent_harness/registry.py`.
- Capability requirement is `"repository_tools"` (all three `SkillTemplate`s already grant this).
- Do NOT grant it to any other Role. Rule #16 is preserved because `ENGINEER.tools` is template data.

### 4.10 Failure taxonomy — no silent completion

`_run_engineer_tool_loop` must translate the new outcomes into structured `TaskState.FAILED` transitions with visible reasons:

- `SelfCorrectionExhaustedError` → Mission FAILED with `reason_code="self_correction_exhausted"` in the `TASK_FAILED` event payload. The reason string includes the total correction attempts and the last validation's summary line.
- `ToolLoopResult` with `stop_reason="employee_surrendered"` → Mission FAILED with `reason_code="employee_surrendered"` and the Employee's stated explanation (bounded through the same `bound_output` policy as any other provider text — never raw).
- Existing failure paths (`BudgetExceededError`, `ToolLoopExhaustedError`, generic exceptions) keep their current behavior — do not conflate.

Both new outcomes preserve the branch (do not auto-rollback the whole attempt) so the CEO or a Sprint 18 memory projection can inspect what the Engineer produced.

### 4.11 Timeline — one new coarse event, no per-call noise

Add exactly one new `EventType`:

```
SELF_CORRECTION_TRIGGERED = "agent.self_correction_triggered"
```

- Emitted once per tool loop, the first time correction interception fires.
- Payload: `{task_id, agent_id, attempts_permitted}`.
- Reason: `"Engineer entered self-correction after a failed validation"`.
- Kind: `system`.

Per-attempt detail lives in `HarnessToolCallORM` (audit table) and in the aggregate view (§4.12). Do NOT emit a Timeline event per correction attempt or per rollback — that would violate the Sprint 16-sanctioned audit-vs-events split (DECISIONS.md #233/#237). The CEO gets a coarse narrative beat; the audit table gets full engineering evidence.

### 4.12 Audit extension — minimum explicit recording, no new table, no schema change

Extend `tasks.service.get_harness_summary` to include:

- `correction_attempts: int` (0 .. MAX_CORRECTION_ATTEMPTS) — the number of correction-cycle intercepts this Mission's tool loop performed
- `rollback_count: int` — the number of `revert_last_patch` calls with `status="success"`
- `surrendered: bool` — whether the loop ended via explicit surrender
- `exhausted: bool` — whether the loop ended via `SelfCorrectionExhaustedError`

**Reconstruction from existing tool-call rows alone is ambiguous.** The correction concept lives in orchestrator state (interception decision), not in any existing tool call — an Employee that just experiments with `apply_patch`+`run_validation` after a failed validation, without ever trying to terminate, has done zero corrections. A pure heuristic ("run_validation failed followed by more tool calls") over-counts. Surrender and exhaustion likewise have no distinguishing signal in existing rows.

**Approved approach — synthetic diagnostic rows in `HarnessToolCallORM`, no schema change.** The orchestrator writes a lightweight audit row for each loop-level event it needs to record, using a reserved `tool_name` prefix `"_loop:"`. Real tools cannot start with underscore (registry-owned, all six start with a lowercase letter), so the prefix cannot collide.

Reserved synthetic tool_names:

- `_loop:correction_interception` — one row per intercepted termination-with-failed-validation. `arguments_summary = {"attempt": N, "max_attempts": MAX_CORRECTION_ATTEMPTS}`, `status = "recorded"`, `output_excerpt = ""`.
- `_loop:correction_exhausted` — one row when `SelfCorrectionExhaustedError` is about to be raised. `arguments_summary = {"attempts": N}`, `status = "recorded"`.
- `_loop:employee_surrendered` — one row when a surrender-marker termination is accepted. `arguments_summary = {"text_length": N}` (never the raw text), `status = "recorded"`, `output_excerpt` = bounded surrender text via `output.bound_output`.

`status = "recorded"` is a new allowed value alongside `"success"|"denied"|"error"`. This does not require a schema change — `status` is a plain `String` column. Update the docstring on `HarnessToolCallORM.status` to enumerate all four values and note that `"recorded"` is orchestrator-diagnostic, never a real handler outcome.

`get_harness_summary` derivations become exact:

- `correction_attempts = count(rows where tool_name = "_loop:correction_interception")`
- `rollback_count = count(rows where tool_name = "revert_last_patch" and status = "success")`
- `surrendered = exists(row where tool_name = "_loop:employee_surrendered")`
- `exhausted = exists(row where tool_name = "_loop:correction_exhausted")`

Update `audit.summarize_arguments` to handle the three new tool_names (pass through the small `{attempt, max_attempts}`/`{attempts}`/`{text_length}` dicts as-is; do not attempt to bound them — they are already server-owned tiny dicts).

Do NOT:
- add a new table,
- add a new column to `HarnessToolCallORM`,
- add a new migration,
- persist raw surrender text (bound it first),
- persist raw validation failure output in these synthetic rows.

If, mid-implementation, this synthetic-row approach turns out to be dishonest for some case (e.g. a race that produces duplicate interception rows), record the anomaly and choose the smallest fix that does not require a schema change. If no fix without a schema change is possible, escalate rather than silently adding a migration.

### 4.13 Cancellation preserves invariants

- `asyncio.CancelledError` remains uncaught by `run_tool_loop`'s `except` clauses (it is `BaseException`, not `Exception`). This is unchanged from Sprint 16 and is a load-bearing invariant.
- Cancellation mid-correction: the reminder message may or may not have been appended; the Employee's next turn may or may not have started. Either way, `CancelledError` at the next `await` propagates; `_run_engineer_tool_loop`'s `except asyncio.CancelledError` block releases the Employee to idle; Mission → CANCELLED. No corrective fabrication.
- Cancellation mid-`revert_last_patch`: git operations are synchronous. If the revert began, it either completed or the process was killed; there is no recovery attempt. Post-cancellation branch state is whatever git left behind; the Reviewer never sees a cancelled Mission's branch (Mission → CANCELLED, no review stage runs). This is consistent with cancellation semantics for `apply_patch` today.

### 4.14 One-shot Engineer path untouched

Everything in §4.1–§4.13 applies to `RoleSpec.harness == "tool_loop"` Roles only. Non-tool_loop Roles are unaffected. The correction mechanism lives entirely inside `agent_harness/orchestrator.py`, its handlers, and the `_run_engineer_tool_loop` engine branch. The `_run_role` one-shot path is not modified.

### 4.15 Mock mode proves the loop with zero keys

Extend `mock_provider.py::_tool_loop_response` with deterministic scenarios selected by markers in the initial user message (mirroring Sprint 12's marker convention and Sprint 16's `_is_rework` marker):

- `SELF_CORRECTION_DEMO`: read → patch → validate (fail) → patch (fix) → validate (pass) → terminate with a change summary.
- `SELF_CORRECTION_ROLLBACK`: read → patch → validate (fail) → revert_last_patch → patch (different fix) → validate (pass) → terminate.
- `SELF_CORRECTION_EXHAUSTED`: read → patch → validate (fail) → patch (still bad) → validate (fail) → patch (still bad) → validate (fail) → attempt to terminate (loop intercepts each time until `MAX_CORRECTION_ATTEMPTS` is exceeded).
- `SELF_CORRECTION_SURRENDER`: read → patch → validate (fail) → terminate with final text containing `**Unable to Complete:** <reason>`.

Simulating "validation failed" from a mock requires the `FakeSandbox` to be steerable. Prefer a small `FakeSandbox` variant (or fixture-only subclass) that returns `status="failed"` for a named profile — do not add a "fail on demand" flag to the real `SandboxRunner` interface. If a `FakeSandbox` variant is impractical, expose the failure only via the mock provider's own scenario branching, not via `TEMPLATE.checks` (keep the template registry clean).

`SELF_CORRECTION_EXHAUSTED` and `SELF_CORRECTION_SURRENDER` may live as orchestrator-level tests via `FakeGateway` instead of full-pipeline mock scenarios if that is simpler; the goal is deterministic coverage of every path, not scenario count parity. Record the choice.

### 4.16 Correction semantics — the load-bearing rule

**The one rule the whole sprint hinges on:**

> **A tool loop must never terminate normally while its most recent `run_validation` returned `status="failed"`.**

Failed validation does NOT immediately force anything. The Employee keeps full agency to call more tools (read, patch, revalidate, roll back) between the failure and its next termination attempt. Only when the Employee tries to terminate does the orchestrator intercept.

Complete decision table for a termination attempt (`result.tool_calls == ()`):

| `last_validation_status` | Surrender marker in text? | `correction_attempts` state | Outcome |
|---|---|---|---|
| any value | yes (`**Unable to Complete:**`) | any | Accept termination. `stop_reason = "employee_surrendered"`. Mission → `FAILED` (reason_code `employee_surrendered`). |
| `"passed"` | no | any | Accept termination. `stop_reason = "end_turn"`. Normal success path. |
| `None` (never called validation) | no | any | Accept termination. `stop_reason = "end_turn"`. Sprint 16 default behavior — unchanged. |
| `"could_not_run"` | no | any | Accept termination. `stop_reason = "end_turn"`. Sandbox unavailability is not a failure signal. |
| `"failed"` | no | `< MAX_CORRECTION_ATTEMPTS` | INTERCEPT. Increment `correction_attempts`. Write `_loop:correction_interception` audit row. On first interception this loop, publish `SELF_CORRECTION_TRIGGERED` event. Append server-owned corrective reminder as a user message. `continue` the loop. |
| `"failed"` | no | `== MAX_CORRECTION_ATTEMPTS` (about to exceed) | Write `_loop:correction_exhausted` audit row. Raise `SelfCorrectionExhaustedError`. |

State transitions during the loop:

- Every successful `run_validation` call updates `last_validation_status` to its resolved status (`passed` / `failed` / `could_not_run`).
- Every successful `revert_last_patch` call clears `last_validation_status` to `None` (branch state changed; the Employee should re-validate).
- No other tool changes `last_validation_status`.
- `correction_attempts` only increments on an INTERCEPT row above. It never decrements. A passing validation between correction cycles does NOT reset it — the count is lifetime-per-loop, not consecutive-streak.

This differs from Sprint 16's `denied_streak`/`malformed_streak` (which reset on success) on purpose: those streaks bound "provider stuck on the same mistake"; correction attempts bound "how many times we'll re-open a Mission the Employee thinks is done."

---

## 5. Architecture Requirements

Prefer boundaries equivalent to:

- `ToolRunContext` (immutable frozen dataclass) gains: `branch_base_sha: str` — recorded once by `_run_engineer_tool_loop` before the loop starts.
- Orchestrator-local mutable state (do NOT mutate `ToolRunContext`): a small `LoopState` object (frozen-field dataclass with mutable fields, or a plain class) holding `last_validation_status: str | None`, `correction_attempts: int`, `first_correction_emitted: bool`, `apply_patch_commit_history: list[str]`. Passed into `dispatch_tool_call` explicitly as a keyword argument — do not smuggle it via `ToolRunContext`.
- The `dispatch_tool_call` signature grows one parameter: `loop_state: LoopState | None = None`. It is only non-None during a tool-loop dispatch and is what `apply_patch` / `run_validation` / `revert_last_patch` handlers read and mutate. Other consumers of `dispatch_tool_call` (there are none today outside the orchestrator, but the shape must permit it) pass `None` and the handlers operate exactly as they do in Sprint 16.
- Handler mutations of `LoopState` are the only place `apply_patch_commit_history` grows and `last_validation_status` changes. The orchestrator never mutates them directly except:
  - `last_validation_status → None` after a successful `revert_last_patch` (the orchestrator does this in the same block that clears rollback bookkeeping, since it needs to happen atomically with the pop).
  - `correction_attempts += 1` at each interception.
  - `first_correction_emitted = True` at first interception.
- New port method: `WorkspaceManager.revert_last_commit(project_id, branch_name, target_sha) -> None`. The `target_sha` argument is server-computed (never provider-derived) and the implementation asserts ancestry before resetting (§4.7).
- New port method OR reused primitive for reading HEAD: prefer `WorkspaceManager.head_sha(project_id, branch_name) -> str` as a proper distinct port method — it is semantically what we need and `diff_stats()` returns a heavier `CommitResult`. If, on inspecting `LocalGitWorkspaceManager`, adding a one-line method feels like unnecessary port surface and `diff_stats().commit_sha` reads cleanly at the two call sites (loop-start `branch_base_sha` capture, post-`apply_patch` head-sha capture), reuse `diff_stats().commit_sha` instead. Record the choice in DECISIONS.md.
- New audit helper: `agent_harness.audit.record_loop_event(session_factory, *, project_id, task_id, agent_id, kind, arguments_summary, output_excerpt="")` that writes a `HarnessToolCallORM` row with `tool_name = f"_loop:{kind}"`, `status = "recorded"`, `duration_seconds = 0.0`, and a fresh generated `call_id`. Used for the three synthetic tool_names in §4.12.
- New tool schema: `RevertLastPatchArgs(ToolArguments)` with no fields.
- New handler: `revert_last_patch` in `agent_harness/handlers.py`.
- New error type: `SelfCorrectionExhaustedError` in `core/errors.py`.
- New event: `EventType.SELF_CORRECTION_TRIGGERED`.
- New optional parameter to `run_tool_loop`: `on_self_correction_triggered: Callable[[], Awaitable[None]] | None = None`. The orchestrator awaits it (if provided) exactly once, on the first interception, before appending the corrective reminder. `_run_engineer_tool_loop` provides a callback that publishes `SELF_CORRECTION_TRIGGERED` via `self._event_bus.publish`; the orchestrator itself does not import `EventBus`.

The orchestrator remains "AgentRuntime integration adapter" (Sprint 16 §5) — it must not become:

- a diff-analysis engine
- a validation-result parser (`run_validation`'s output is text; the orchestrator only reads `dispatch_tool_call`'s `status`, not the text body)
- a Reviewer replacement
- a self-correction across missions or specifications (that is Sprint 18)
- a git-log analyzer

Keep pure logic (correction interception decision, rollback bounds check, surrender-marker detection) separately testable via a scripted `FakeGateway`, mirroring `test_agent_harness_orchestrator.py`.

---

## 6. Persistence and Audit

- `HarnessToolCallORM` is extended only if §4.12's derivation-from-rows approach is not honest. If a new column is required (`outcome_marker` or equivalent), add a proper Alembic migration on top of `b1f4c8d5e9a2` with round-trip verification.
- Do not persist provider surrender text raw. Bound it via `output.bound_output` before it enters any DB row or event payload.
- `revert_last_patch` calls persist to `HarnessToolCallORM` like every other tool call — status `success` or `denied` or `error`, `arguments_summary` = `{}` (the tool has no arguments), `output_excerpt` = the confirmation text.
- No new event families beyond §4.11.

---

## 7. AgentRuntime Integration

Extend `run_tool_loop` to:

1. **Construct `LoopState`** at loop start (see §5). Owned by the orchestrator, mutated by handlers.
2. **Track `last_validation_status`.** `run_validation`'s handler is extended so that on a completed sandbox run it writes the resolved status (`"passed"` | `"failed"` | `"could_not_run"`) into `loop_state.last_validation_status`. The status value inspected here is the `SandboxRunner.CheckResult.status`, not text parsed from output. On `run_validation` handler exceptions (unknown profile, execution disabled, etc.), leave `last_validation_status` unchanged — those are `ToolDeniedError` / string-return cases already, not validation outcomes.
3. **Track `apply_patch_commit_history`.** `apply_patch`'s handler is extended so that after a successful commit (i.e. `write_files.written` non-empty AND the resulting HEAD sha differs from the pre-call HEAD — the byte-identical no-op guard, §4.8) it appends the new HEAD sha to `loop_state.apply_patch_commit_history`. HEAD reading uses whichever primitive §5 selects.
4. **Termination interception.** On `result.tool_calls == ()`, apply the §4.16 decision table exactly. Surrender-marker detection is a lenient regex on `result.text` only (never on tool_result blocks), same convention `parse_verdict` uses.
5. **Interception side effects (in order):**
   - Write `_loop:correction_interception` audit row via `audit.record_loop_event` (§5).
   - Increment `loop_state.correction_attempts`.
   - If `not loop_state.first_correction_emitted`, `await on_self_correction_triggered()` if provided, then set `loop_state.first_correction_emitted = True`.
   - Append the server-owned corrective reminder as a user message.
   - `continue` the loop.
6. **Exhaustion.** When the incremented `correction_attempts` would exceed `MAX_CORRECTION_ATTEMPTS`, do NOT increment or write an interception row for this attempt; instead write `_loop:correction_exhausted` and raise `SelfCorrectionExhaustedError`. This keeps `correction_attempts` capped at `MAX_CORRECTION_ATTEMPTS` in the audit table.
7. **Surrender.** On surrender-marker detection, write `_loop:employee_surrendered` (with the bounded surrender text as `output_excerpt`) BEFORE returning. Return with `stop_reason = "employee_surrendered"`.
8. **`revert_last_patch` bookkeeping.** After the handler's success return, the orchestrator (not the handler) pops the last entry from `loop_state.apply_patch_commit_history` and sets `loop_state.last_validation_status = None`. This bookkeeping lives in the orchestrator because it is orchestrator-state, not handler-state — the handler already performed the actual git reset.

Provider output is untrusted end-to-end. The corrective reminder message is a code-level constant; the surrender text is bounded before it enters any audit row or event payload; the target SHA passed into `revert_last_commit` is server-computed from `loop_state` never provider-supplied.

---

## 8. Mission and Workflow Integration

`_run_engineer_tool_loop` in `workflow_engine/engine.py`:

1. Compute `branch_base_sha` immediately after `create_branch` completes — before the `run_tool_loop` call.
2. Populate `ToolRunContext.branch_base_sha` with it.
3. Pass an event-emit callback into `run_tool_loop` (`on_self_correction_triggered: Callable[[], Awaitable[None]] | None`) so the orchestrator can trigger the `SELF_CORRECTION_TRIGGERED` publish without importing EventBus.
4. Catch `SelfCorrectionExhaustedError` explicitly and route to `_fail_task_with_reason_code(task_id, "self_correction_exhausted", detail_reason)` — a new small helper mirroring `_fail_task` but adding a `reason_code` to the `TASK_FAILED` payload.
5. Recognize `ToolLoopResult.stop_reason == "employee_surrendered"` and route to `_fail_task_with_reason_code(task_id, "employee_surrendered", surrender_text)`.
6. Preserve the branch in both cases (do not delete or auto-reset it — the Reviewer role does not run, but the branch remains for post-mortem/future memory).
7. All existing invariants:
   - Specification approval gate untouched.
   - Central Employee resolver untouched.
   - Per-Employee model/skill config untouched.
   - Cancellation cleanup unchanged.
   - Mission-level budget guard still runs before every stage.
   - `_land_tool_loop_changes` and `_run_checks` continue to run on success paths.

Rule #16: dispatch on `stage.kind == "produce"` and `role_spec.harness == "tool_loop"` only (already the case).

---

## 9. API and Dashboard Scope

Backend:

- Extend `GET /api/tasks/{task_id}/harness-summary` response to include the new aggregate fields (§4.12): `correction_attempts`, `rollback_count`, `surrendered`, `exhausted`.
- Extend the `HarnessSummaryResponse` Pydantic schema in `tasks/schemas.py` to match.
- No new public endpoints. No arbitrary tool execution endpoint. No public revert endpoint. No public harness-run control endpoint.
- The `SELF_CORRECTION_TRIGGERED` event flows through the existing SSE stream automatically once `EventType` is registered and TS schemas are regenerated.

Frontend — **no UI changes this sprint.** Explicit:

- **No new widget.** Do not add a `SelfCorrectionSummary` widget or any other widget to `workspace_widgets/registry.py`.
- **No `MissionDetail.tsx` change.** Do not surface `correction_attempts` / `rollback_count` / `surrendered` / `exhausted` in the mission detail view.
- **No CEO Workspace shell change.**
- **No new dashboard page or route.**
- **The only allowed frontend change** is regenerating TS event schemas (`python scripts/generate_ts_schemas.py`) so `SELF_CORRECTION_TRIGGERED` is a known event type in `packages/event-schemas/ts/`, plus whatever automatic type edits `lib/api.ts`/`lib/types.ts` require to keep `HarnessSummaryResponse` in sync with the extended backend schema (TypeScript compile error → fix the type; do not render the new fields anywhere).

Rationale: Sprint 16 accepted the same tradeoff for the original `harness-summary` endpoint (DECISIONS.md #238) — it exists but is unrendered. Extending that endpoint follows the same pattern. A CEO-facing self-correction surface is a legitimate Sprint 18+ product decision that belongs with the Memory work (an Employee's failure/correction history is exactly what Sprint 18 will project), not a bolt-on here.

If, mid-implementation, some TypeScript file becomes unable to compile without a rendering change, **prefer breaking that file's optional rendering rather than adding a new visual surface** — record the choice and file it as a Sprint 18 follow-up in `PROGRESS.txt`.

---

## 10. Required Threat / Behavioral Tests

Add tests, following existing patterns (`test_agent_harness_*`, `test_code_missions`, `test_reliability`):

### Correction interception
- Terminating with `last_validation_status == "passed"` returns normally, no correction.
- Terminating with `last_validation_status == "failed"` triggers correction; a reminder message is appended; the loop continues.
- Correction resets when a subsequent `run_validation` passes.
- `correction_attempts` reaches `MAX_CORRECTION_ATTEMPTS` and the next intercepted termination raises `SelfCorrectionExhaustedError`.
- `SELF_CORRECTION_TRIGGERED` is published exactly once per loop even across multiple intercepted terminations.
- An Employee that never calls `run_validation` at all terminates normally.

### Explicit surrender
- A final text containing `**Unable to Complete:** ...` terminates the loop regardless of `last_validation_status`.
- The result carries `stop_reason == "employee_surrendered"`.
- Surrender is detected via lenient regex (case-insensitive, trailing content preserved as diagnostic).
- Surrender text is bounded before persisting or emitting; oversized text is truncated with an explicit marker.

### Rollback
- `revert_last_patch` with an empty `apply_patch_commit_history` raises `ToolDeniedError`.
- `revert_last_patch` after one successful `apply_patch` reverts to `branch_base_sha`.
- `revert_last_patch` after two successful `apply_patch`es reverts to the previous commit's sha.
- `revert_last_patch` after a byte-identical no-op patch reverts the last real patch (§4.8).
- The reverted branch's `diff_stats().commit_sha` matches the recorded target sha.
- Rollback consumes one tool-call budget slot.
- Rollback clears `last_validation_status` (a post-rollback termination attempt does NOT trigger correction on the pre-rollback validation state).
- Rollback denied for a Role without `"revert_last_patch"` in its tools.
- Rollback denied outside the `produce` stage.
- Rollback denied on a cancelled loop (any tool call is denied on a cancelled loop — existing Sprint 16 invariant).
- Rollback cannot cross `branch_base_sha`: attempting a second rollback when history is already empty raises `ToolDeniedError`.

### Failure taxonomy
- `SelfCorrectionExhaustedError` in `_run_engineer_tool_loop` transitions the Mission to `FAILED`, publishes `TASK_FAILED` with `reason_code == "self_correction_exhausted"`, and preserves the branch.
- Employee surrender in `_run_engineer_tool_loop` transitions the Mission to `FAILED`, publishes `TASK_FAILED` with `reason_code == "employee_surrendered"`, and preserves the branch.
- Existing `BudgetExceededError` and `ToolLoopExhaustedError` paths still transition to `BLOCKED` / `FAILED` respectively with unchanged payloads.
- Employee is released to `IDLE` in all three exhaustion paths (§4.10).

### Audit / observability
- Every `revert_last_patch` call produces exactly one `HarnessToolCallORM` row with `status` in `{success, denied, error}`.
- `get_harness_summary` returns the correct `correction_attempts`, `rollback_count`, and `surrendered` for representative fixtures.
- Reviewer receives the corrected diff + change summary + check summary when correction succeeds; the Reviewer stage is skipped entirely when the Mission fails via exhaustion or surrender.

### Cancellation
- Cancelling a Mission during a correction cycle transitions to `CANCELLED`, not `FAILED`; the Employee is released; no late correction fabrication.
- Cancelling immediately before a `revert_last_patch` cannot leave the branch in a partial state that would corrupt a re-run.

### Integration
- Deterministic mock scenarios (`SELF_CORRECTION_DEMO`, `SELF_CORRECTION_ROLLBACK`, `SELF_CORRECTION_EXHAUSTED` if applicable) drive the pipeline end-to-end with zero provider keys.
- Existing `test_code_missions.py` and `test_reliability.py` remain green — the default mock tool-loop fixture (no marker) does not trigger correction and produces exactly Sprint 16 behavior.
- Role-hardcoding guard remains green (no new `if role_key ==` branches introduced).
- Full-suite regression: 455 baseline + new tests.

---

## 11. Phases

### Phase 0 — Baseline verification and architecture decisions

1. Verify HEAD, origin/master, working tree clean.
2. Run backend baseline (`make test` or `pytest` against `apps/api`). Confirm 455 passed / 6 skipped.
3. Run dashboard typecheck (`tsc --noEmit`) and build (`next build`). Confirm 19 routes.
4. Verify Alembic head is `b1f4c8d5e9a2` and migration round-trip is clean.
5. Run a mock code mission end-to-end with zero provider keys (existing tests already cover this — confirm they pass).
6. Read every file listed in §3.
7. Inspect the current `run_tool_loop` termination path; identify the exact line where interception must happen.
8. Inspect the current `run_validation` handler; decide the shape of the structured pass/fail signal (§7.1).
9. Inspect `LocalGitWorkspaceManager` for reset/revert semantics; decide `revert_last_commit` implementation.
10. Decide §4.12: derived-from-rows vs new nullable column. Record the decision.
11. Decide §4.15: mock-scenario implementation (steerable `FakeSandbox` vs profile-name convention).
12. Decide surrender marker exact regex.
13. Decide whether any dashboard change is in scope for this sprint (default: no).
14. Replace/append PROGRESS.txt with Sprint 17 live checklist.
15. Record non-obvious decisions in DECISIONS.md (new entries starting at #239).
16. Commit/push Phase 0 checkpoint.

### Phase 1 — Failure-aware loop + correction enforcement

1. Add `SelfCorrectionExhaustedError` to `core/errors.py`.
2. Add `EventType.SELF_CORRECTION_TRIGGERED` to `core/events/types.py`.
3. Add `branch_base_sha: str` field to `ToolRunContext`.
4. Extend `run_validation` handler to convey pass/fail structurally (either via a distinct return shape or a distinguished status the orchestrator can read from `dispatch_tool_call`).
5. Add correction-tracking state to `run_tool_loop`: `last_validation_status`, `correction_attempts`, `first_correction_emitted`, `apply_patch_commit_history`. Do not mutate `ToolRunContext`.
6. Add surrender-marker detection utility.
7. Add corrective reminder message (server-owned code constant).
8. Add optional `on_self_correction_triggered` callback parameter to `run_tool_loop`.
9. Implement termination interception logic per §7.
10. Unit tests for correction lifecycle (via extended `FakeGateway` scenarios): triggered on failed-validation termination, reset on subsequent pass, exhaustion, surrender path, no-validation normal termination, event emitted exactly once.
11. Update PROGRESS.txt.
12. Commit/push Phase 1.

### Phase 2 — Rollback tool

1. Add `WorkspaceManager.revert_last_commit(project_id, branch_name, target_sha) -> None` abstract method.
2. Implement in `LocalGitWorkspaceManager` using safe argv-list git commands (`checkout` + `reset --hard target_sha`). No shell.
3. Add `WorkspaceManager.head_sha(project_id, branch_name) -> str` (or reuse `diff_stats().commit_sha` — decide which is cheapest and cleanest).
4. Track `apply_patch_commit_history` inside `run_tool_loop` (append post-dispatch when head sha changed).
5. Add `RevertLastPatchArgs(ToolArguments)` schema with no fields.
6. Add `REVERT_LAST_PATCH` `ToolDefinition`; add to `TOOLS`, `TOOLS_BY_KEY`, `WRITE_TOOL_KEYS`.
7. Add `"revert_last_patch"` to `ENGINEER.tools` in `app/templates/software_company.py`.
8. Implement `revert_last_patch` handler in `agent_harness/handlers.py` with the denial cases from §4.7.
9. Add tests covering every §10 "Rollback" case.
10. Verify role-hardcoding guard still passes.
11. Verify existing `test_code_missions.py` and `test_reliability.py` still pass (no correction triggered, no rollback used — default behavior identical).
12. Update PROGRESS.txt.
13. Commit/push Phase 2.

### Phase 3 — Mission integration + audit aggregate + mock scenarios

1. Extend `_run_engineer_tool_loop` to compute `branch_base_sha` (via the primitive chosen in Phase 0) immediately after `create_branch` and pass it into `ToolRunContext`.
2. Construct the `LoopState` and pass it into `run_tool_loop`.
3. Pass an `on_self_correction_triggered` callback that publishes `SELF_CORRECTION_TRIGGERED` via `self._event_bus.publish`.
4. Extend `_fail_task` (or add `_fail_task_with_reason_code`) to accept a structured `reason_code` and include it additively in the `TASK_FAILED` payload — existing consumers must remain unaffected (`reason_code` is a new optional field, `reason` string is unchanged).
5. Catch `SelfCorrectionExhaustedError` explicitly in `_run_engineer_tool_loop`'s `except` (ordered before the generic `except Exception`, mirroring how `BudgetExceededError` is caught explicitly in `_run_pipeline`).
6. Recognize `stop_reason == "employee_surrendered"` in `_run_engineer_tool_loop` and route to `_fail_task_with_reason_code("employee_surrendered", bounded_surrender_text)`.
7. Bound the surrender text via `output.bound_output` before it enters the `TASK_FAILED` payload OR the `_loop:employee_surrendered` audit row (both consumers get the bounded text).
8. Preserve the branch on both new failure paths — no auto-rollback, no auto-cleanup.
9. Employee is released to `IDLE` on both new failure paths via the same `_release_agent_to_idle` walk already used by Sprint 16 exception paths.
10. Extend `tasks.service.get_harness_summary` with `correction_attempts`, `rollback_count`, `surrendered`, `exhausted` computed via the §4.12 synthetic-row queries. Extend `HarnessSummaryResponse` in `tasks/schemas.py` to match.
11. **No migration.** §4.12's synthetic-row approach requires zero schema change. If Phase 0 concluded otherwise, revisit before writing a migration.
12. Add mock scenarios in `mock_provider.py::_tool_loop_response` per §4.15. Wire a steerable `FakeSandbox` variant (test-only subclass or fixture-scoped injection) if the scenarios require a `run_validation` failure — do NOT touch the real `SandboxRunner` interface or `TEMPLATE.checks`.
13. Regenerate TS event schemas (`python scripts/generate_ts_schemas.py`). Fix any TypeScript compile errors from the extended `HarnessSummaryResponse` shape by updating type declarations only — do not render the new fields (§9).
14. Integration tests: end-to-end pipeline runs for each new scenario; assertions on Mission state, `TASK_FAILED` payload (including new `reason_code`), `SELF_CORRECTION_TRIGGERED` event presence and payload, `HarnessToolCallORM` audit rows (including `_loop:*` synthetic rows), `get_harness_summary` aggregate correctness.
15. Verify Reviewer flow still receives real diff/evidence on the corrected-success path.
16. Verify the default (no marker) mock flow is unchanged — Sprint 16 code-mission tests all green with zero modifications.
17. Update PROGRESS.txt.
18. Commit/push Phase 3.

### Phase 4 — Regression, security audit, documentation, and close-out

1. Run full backend suite. Target: 455 baseline + Sprint-17 new tests, zero regressions outside Sprint 17.
2. Run dashboard `tsc --noEmit` + `next build`. Confirm regenerated event types compile.
3. Verify migration chain (if a migration was added) via `alembic heads`/`history` and a real Postgres round-trip through `scripts/seed.py`.
4. Run mock E2E with zero provider keys covering the three new scenarios.
5. Run existing planning / specification / mission / workspace / widget regressions.
6. Independent security audit (dedicated read-only agent, not self-audit):
   - `revert_last_patch` cannot cross `branch_base_sha`.
   - `revert_last_patch` cannot affect any branch other than the loop's mission branch.
   - `revert_last_patch` uses argv-list git (no `shell=True`, no string interpolation).
   - Correction cannot bypass mission-level budget (`_check_budget` still runs).
   - Correction cannot bypass tool-call/wall-time budget.
   - Employee surrender text is bounded before persisting/emitting; no raw provider text reaches the DB or SSE payload.
   - No silent completion on failed validation.
   - `SELF_CORRECTION_TRIGGERED` payload contains no secrets or file content.
   - `get_harness_summary` still exposes only bounded aggregates (no raw content).
   - Reviewer never sees a Mission that failed via exhaustion/surrender.
   - Role-hardcoding guard clean (no new role-name literals introduced).
   - No new public arbitrary-execution endpoint exists.
7. Inspect the full diff for scope leakage (Sprint 18 memory features, new Roles, dashboard restructure).
8. Documentation sync:
   - `CLAUDE.md` roadmap row 17 → "17 ✅".
   - `docs/ARCHITECTURE.md` §4.6 rewritten to match as-built self-correction (previously wrote it as an intended target — must now describe reality, per Rule #10).
   - `docs/DECISIONS.md` new entries #239+ covering the correction-trigger point, MAX_CORRECTION_ATTEMPTS choice, surrender marker choice, rollback bounds, event-vs-audit split extension, and any non-obvious phase decision.
   - `README.md` status paragraph updated only if a CEO-facing user-visible change landed.
   - `docs/design/UX_SPEC.md` updated only if any dashboard change landed.
   - `FOR_CTO.md` §7.12, §12, §13, §18, §19 updated for Sprint 17 outcomes.
9. Record residual limitations honestly (e.g. "no cross-run learning — Sprint 18", "rollback is per-patch not per-attempt", "surrender detection is regex-based, provider can theoretically evade by rewording — bounded impact since exhaustion still fires").
10. Record Sprint 18 boundaries and deferrals in DECISIONS.md close-out entry.
11. Final commit / push.
12. Verify clean working tree.
13. Verify local HEAD == origin/master.

---

## 12. Definition of Done

Sprint 17 is complete only when:

1. Baseline is verified before any code change (455 passed / 6 skipped, dashboard typecheck/build green, Alembic head `b1f4c8d5e9a2`).
2. `run_validation` outcomes are structured signals stored in `LoopState.last_validation_status`, sourced from `CheckResult.status` (never parsed from output text).
3. Correction interception fires exactly per §4.16's decision table.
4. `MAX_CORRECTION_ATTEMPTS = 3` bounds the correction loop; the constant lives in `agent_harness/orchestrator.py`.
5. Corrective reminder text is a server-owned code constant, never provider-supplied.
6. Explicit Engineer surrender is recognized via a lenient case-insensitive regex on the terminating `result.text` only and produces `stop_reason == "employee_surrendered"`.
7. `revert_last_patch` exists as a first-party tool in the immutable registry, and only there.
8. `revert_last_patch` is granted only to `ENGINEER`, only through `RoleSpec.tools`.
9. `revert_last_patch` has zero provider-supplied arguments (Pydantic schema with no fields, `extra="forbid"`).
10. Every rollback safety requirement in §4.7 (1–10) holds — verified individually by tests, not only by inspection.
11. Rollback target SHA is server-computed from `LoopState.apply_patch_commit_history` and `ToolRunContext.branch_base_sha`; never accepted from the provider.
12. `WorkspaceManager.revert_last_commit` uses `shell=False` argv-list git and asserts ancestry (`git merge-base --is-ancestor`) before resetting.
13. Rollback clears `LoopState.last_validation_status` and pops the last entry from `apply_patch_commit_history`, both in the orchestrator (not the handler).
14. Rollback consumes one tool-call budget slot.
15. Byte-identical no-op `apply_patch` calls are never appended to `apply_patch_commit_history` (detected via pre/post HEAD sha comparison, not via handler return string).
16. `SelfCorrectionExhaustedError` exists and is caught explicitly by `_run_engineer_tool_loop`.
17. Mission failure via exhaustion produces `TASK_FAILED` with `reason_code == "self_correction_exhausted"` (additive payload field; `reason` string unchanged).
18. Mission failure via surrender produces `TASK_FAILED` with `reason_code == "employee_surrendered"` and the bounded surrender text as the diagnostic.
19. Surrender text is bounded via `output.bound_output` before entering any DB row or SSE payload.
20. Both new failure paths preserve the mission branch (no auto-rollback, no auto-cleanup).
21. `SELF_CORRECTION_TRIGGERED` event exists, is registered in `EventType`, and is published exactly once per loop that entered correction, via a callback injected into `run_tool_loop` (orchestrator does not import `EventBus`).
22. No per-call correction/rollback Timeline event is published (audit-vs-events split preserved).
23. `HarnessToolCallORM` audit rows are written for every `revert_last_patch` call (success/denied/error) via the existing `dispatch_tool_call` finally-block.
24. Synthetic `_loop:correction_interception` / `_loop:correction_exhausted` / `_loop:employee_surrendered` audit rows are written per §4.12 via `audit.record_loop_event`.
25. `HarnessToolCallORM.status` docstring is updated to include `"recorded"` alongside `"success"|"denied"|"error"`.
26. `audit.summarize_arguments` handles the three synthetic tool_names.
27. `get_harness_summary` exposes `correction_attempts`, `rollback_count`, `surrendered`, `exhausted` computed from the synthetic-row queries in §4.12.
28. `HarnessSummaryResponse` in `tasks/schemas.py` is extended to match.
29. **No new table, no new column, no new migration.** Alembic head remains `b1f4c8d5e9a2`.
30. Permission intersection (`harness_enabled ∩ RoleSpec.tools ∩ SkillTemplate.capabilities ∩ stage_kind=="produce" ∩ workspace_ready`) is unchanged in shape and covers the new tool.
31. Cancellation propagates uncaught during correction and during rollback (`asyncio.CancelledError` is `BaseException`, never caught by `except (ToolDeniedError, ...)`).
32. Mission-level budget guard (`_check_budget`) still runs before every stage.
33. Tool-call and wall-time budgets still bound the loop.
34. Existing Sprint 16 tool authorization / path safety / patch atomicity / process isolation / output redaction guarantees are unchanged.
35. Role-hardcoding AST guard (`test_role_hardcoding_guard.py`) remains green.
36. Default mock tool-loop scenario (no marker) produces exactly Sprint 16 behavior — zero modifications to existing `test_code_missions.py` / `test_reliability.py` / `test_approval_flow.py` and all pass unchanged.
37. Deterministic mock proves correction success, rollback success, correction exhaustion, and explicit surrender (via mock scenarios and/or orchestrator-level `FakeGateway` tests) with zero provider keys.
38. Reviewer receives real diff + change summary + check summary on the corrected-success path.
39. Reviewer stage is skipped entirely when the Mission fails via exhaustion or surrender.
40. Employee is released to `IDLE` on both new failure paths via the same `_release_agent_to_idle` walk Sprint 16 uses.
41. Full backend suite passes (455 baseline + new tests, zero regressions outside Sprint 17 files).
42. Dashboard typecheck/build pass after TS schema regeneration; **no new widget, no `MissionDetail.tsx` change, no CEO Workspace shell change** (§9).
43. Full mock E2E with zero keys passes covering all new scenarios.
44. Existing planning / workspace / widget / mission behavior remains functional.
45. Independent security audit (dedicated agent, not self-audit) finds zero CONCERN/FAIL items across the §11 Phase 4 audit list.
46. `CLAUDE.md` (roadmap row 17 → "17 ✅"), `docs/ARCHITECTURE.md` §4.6, `docs/DECISIONS.md` (new entries #239+), `FOR_CTO.md` (§7, §12, §13, §18, §19) synchronized in the same commits as the code.
47. No Sprint 18+ scope (cross-run learning, memory recall, cross-mission correction, second harness Role, Reviewer-driven auto-fix, dashboard surface for correction stats) leaked into the diff.
48. Residual limitations are recorded honestly (surrender-marker regex evasion, per-patch not per-attempt rollback, single-branch scope, sandbox-unavailability interaction, no CEO-facing surface).
49. Final commits are pushed.
50. Local HEAD equals origin/master.

Do not claim browser verification unless a browser was actually used. Sprint 16-style "UNVERIFIED, no CEO-facing UI change this sprint" is the correct honest classification for Sprint 17 (per §9's hard no-UI decision).

---

## 13. Out of Scope

Do not implement:

- Cross-attempt or cross-Mission learning (Sprint 18).
- Organizational Memory (Sprint 18).
- Retrieval of prior missions' failure patterns (Sprint 18).
- Auto-fix triggered by Reviewer feedback (that path stays CEO Decision → `request_changes`).
- Escalation policies (Sprint 12/13 territory; §4.4 of ARCHITECTURE.md is still "not yet scheduled").
- Extending `harness == "tool_loop"` to any Role beyond Engineer.
- New harness tools other than `revert_last_patch` (no `git_diff_range`, no `git_log`, no `checkpoint`, no `apply_patch_hunks`, no arbitrary git).
- Unrestricted shell, arbitrary command execution, arbitrary executable, arbitrary flags, arbitrary network, package installation.
- Any provider expansion (still Mock + Anthropic).
- New CEO Workspace shell layout.
- Widget marketplace, third-party plugins.
- Approval workflow changes.
- New Roles (no Designer/QA/DevOps this sprint).
- Multi-user collaboration on one Company.
- Cloud deployment or production hardening (Sprint 19).
- Any migration that changes an existing column's shape.
- Any breaking change to `TASK_FAILED` consumers (extend payload additively).

If a Sprint 18/19 need appears mid-implementation, record it as a follow-up in `PROGRESS.txt`'s handoff notes — do not implement it here.

---

## 14. Final Report

Return one evidence-based report containing:

1. Starting / final / origin SHA and working-tree state
2. Sprint result and DoD checklist count (46 items)
3. Commits and their rationale
4. Any repository divergences discovered
5. Threat model and trust boundaries (delta from Sprint 16 §2)
6. Correction and rollback design (attempt limit, trigger point, surrender mechanism, rollback bounds)
7. Permission calculation (unchanged — cite the intersection)
8. Workspace/path/symlink protections (unchanged — cite the audit)
9. Patch/rollback safety, atomicity, and branch-base confinement
10. Process execution and environment controls (unchanged from Sprint 16)
11. Budgets, idempotency, cancellation (delta: MAX_CORRECTION_ATTEMPTS + budget interaction)
12. Output redaction/truncation (delta: surrender text bounding)
13. Audit persistence and observability (delta: new aggregate fields, single new event type, no new event families)
14. AgentRuntime and mission integration (delta: new termination outcomes)
15. Mock harness E2E for correction success, rollback success, and exhaustion
16. Security audit results with file/line evidence
17. Migration status (either "no migration needed" or migration + round-trip evidence)
18. Verification matrix (baseline → post-Phase-N test counts, dashboard typecheck/build, mock E2E)
19. Starting/ending test counts and modified-test classification
20. Existing-feature compatibility (planning, specifications, missions, workspace, widgets)
21. Documentation updates (CLAUDE.md, ARCHITECTURE.md, DECISIONS.md, FOR_CTO.md, README/UX_SPEC only if user-visible changes landed)
22. Residual risks and low-confidence areas (surrender-marker evasion, single-branch scope, sandbox unavailability interaction)
23. Scope control and Sprint 18 handoff
24. Final state (clean tree, HEAD == origin/master)

Begin with Phase 0 and continue through Phase 4 without routine confirmation.
