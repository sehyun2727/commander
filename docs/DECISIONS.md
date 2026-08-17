# Decisions Log — Sprint 3 ("Make It Real")

Judgment calls made while building the vertical slice, in the order they
came up. Each one only exists because the brief left it open or because
existing Sprint 0-2 skeleton conflicted with the Sprint 3 spec (spec wins,
per the brief's constraints).

## Phase 1 — Contracts

1. **Event contracts moved from per-type frozen dataclasses to a single
   Pydantic v2 `Event` envelope with a JSON `payload`.** The Sprint 1/2
   skeleton had one dataclass subclass per event type with typed fields.
   Sprint 3's persistence decision is a single unified event-stream table,
   which means the DB column is JSON either way — keeping 30 dataclass
   subclasses added no type safety the DB round-trip couldn't already lose,
   and blocked easy TS codegen. Payload shape safety is preserved via
   `PAYLOAD_MODELS` (one Pydantic model per `EventType`) validated in
   `build_event()`.
2. **`kind` is inferred by `build_event()`** (`conversation` only for
   `conversation.message`, `system` otherwise) unless explicitly overridden
   — callers shouldn't have to repeat it for every system event.
3. **TS codegen is hand-rolled** (`scripts/generate_ts_schemas.py` walks
   `model_fields` directly) instead of using `pydantic2ts` or
   `datamodel-code-generator`. Both need either a Node subprocess or extra
   deps that aren't guaranteed to resolve offline; walking fields directly
   needed no new dependency and is ~120 lines.
4. Added `EventType.AGENT_CREATED`, `APPROVAL_CHANGES_REQUESTED`, and
   `SYSTEM_HEARTBEAT` — not in the original Sprint 1 enum but required by
   the Sprint 3 workflow (agent creation on company bootstrap, the CEO's
   third decision option, and SSE heartbeats).
5. Reused `AgentState`/`TaskState`/`AGENT_TRANSITIONS`/`TASK_TRANSITIONS`
   from Sprint 2 unchanged — they already match the Sprint 3 spec's agent
   lifecycle exactly.

## Phase 2 — Backend core

6. **Added two modules with no owner in the Sprint 1/2 module list:
   `tasks` (Mission CRUD, assignment, Meeting messages) and `realtime`
   (SSE fan-out).** Neither existed as a concept until Sprint 3's task
   pipeline and dashboard-streaming requirements; splitting them out kept
   `workflow_engine` focused on orchestration instead of also owning HTTP
   routes and request/response schemas.
7. **Failure handling is scoped down to "catch the exception, mark the
   Mission `failed`, publish `TaskFailed`."** `core/errors.py`'s full
   `CommanderError` hierarchy (timeout/model-unavailable/workspace-conflict
   retry-and-escalate policy) described in
   `docs/backend/workflow/FAILURE_HANDLING.md` is a larger state machine
   than a one-session vertical slice needs; the minimal version still lets
   every failure surface as a Timeline event and a terminal Mission state,
   which is what the Definition of Done actually requires. Wiring the full
   policy is left as a follow-up.
8. **Secrets are DB-backed with an env fallback, not env-only.** The spec
   asks for a Company Settings field where the CEO can paste an Anthropic
   API key through the UI, which means the value has to be writable at
   runtime — a `.env`-only `SecretsProvider` can't support that. Added a
   `settings_kv` table (`DBSecretsProvider`) that checks the DB first and
   falls back to the `pydantic-settings` `.env` value for
   `ANTHROPIC_API_KEY`, so both "set it in `.env` before boot" and "paste
   it in Company Settings" work through the same port.
9. **`workflow_engine`'s CEO-decision handling covers exactly three
   outcomes** (approve → Mission `completed`; reject → Mission
   `cancelled`; request_changes → attempt+1, Mission back to
   `in_progress`, Engineer re-runs) — matching the spec's three-button
   CEO Decision UI one-to-one, instead of a more general revision-history
   model.

## Phase 3 — Provider layer

10. **Reviewer verdicts are parsed from a trailing `**Verdict:** Approved`
    / `**Verdict:** Changes requested` line in the completion text**,
    shared by both `MockProvider` and `AnthropicProvider`. This keeps
    `workflow_engine` provider-agnostic — it never branches on which
    provider produced the text, only on the parsed verdict — and means
    swapping `COMMANDER_PROVIDER=mock` → `anthropic` requires no workflow
    code changes, only a system-prompt instruction (already baked into
    each agent's persona) telling the model to end with that line.
11. **`model_registry` maps logical refs (`planner-default`,
    `builder-default`, `reviewer-default`) to concrete `(provider, model)`
    pairs**, rather than letting callers name a model directly. This is
    what makes `COMMANDER_PROVIDER=mock` the default with zero API key
    required — call sites never know or care which concrete model backs
    a role.

## Phase 4 — Realtime

12. **SSE, not WebSocket**, confirmed per the brief's existing decision —
    implemented as a single `GET /api/events/stream?project_id=` endpoint
    that replays the last 50 persisted events (via `EventBus.recent`) then
    switches to a live per-connection `asyncio.Queue` registered on the
    bus, with a 15s heartbeat comment so idle proxies/browsers don't drop
    the connection. Verified manually: replay returns historical events
    immediately on connect, and the queue clears its registration in a
    `finally` block on client disconnect.

## Phase 5 — Dashboard frontend

13. **`http://127.0.0.1:3000` added to `cors_origins` alongside
    `http://localhost:3000`.** Browsers treat these as distinct origins
    even though they resolve to the same machine; the dev server was
    being hit via `127.0.0.1` in local testing, which the API rejected.
    Both are now allowlisted by default.
14. **Meetings are task-scoped, not agent-scoped.** The spec sketches
    `/company/[id]/meetings/[agentId or taskId]`, but the backend's
    message model (`GET/POST /api/tasks/{task_id}/messages`) is keyed on
    the task, and `post_message` already resolves "whichever agent
    currently holds the task" server-side. The Meetings route is
    implemented as `/company/[id]/meetings/[taskId]`, sharing the same
    `MissionDetail` component used by the Missions detail route, rather
    than inventing a parallel agent-scoped chat model.
15. **Realtime state uses TanStack Query invalidation, not a live cache
    merge.** `RealtimeProvider` keeps a small rolling buffer (last 100
    events) purely for the Timeline feed's live narration, but on each
    incoming SSE event it invalidates the relevant query keys (missions,
    employees, approvals, timeline, and — if the event carries a
    `task_id` — that mission's detail/messages) rather than hand-patching
    query cache entries. Simpler and less error-prone than reimplementing
    cache updates per event type, at the cost of an extra refetch per
    event; acceptable at this scale.
16. **Verified in a real headless browser, not just `next build`.**
    Installed Playwright into a scratch temp directory (not a project
    dependency) to navigate all six pages against the live API and assert
    zero console/page errors — `tsc --noEmit` and `next build` passing
    doesn't catch runtime issues like CORS rejections or hydration
    errors. Confirmed clean on landing, Headquarters, Missions, mission
    detail, Employees, and Company Settings.

## Phase 6 — Seed, DX, verification

17. **`scripts/seed.py` deletes the dev sqlite file and rebuilds it from
    scratch every run**, rather than being idempotent/additive. `make
    seed` is meant to hand back a known-good demo state on demand, and a
    fresh company each time is simpler and more predictable than
    reconciling against whatever was left from manual testing or a prior
    demo. It also drives the *real* service layer (`create_project`,
    `create_task`, `assign_task`, `approvals.decide`) rather than
    inserting rows directly — the seeded history is produced by the same
    code path a real CEO session uses, so it can't drift from actual
    behavior.
18. **The seed script chooses one mission per CEO Decision outcome**
    (approved first try, approved after changes requested, rejected) plus
    one already sitting at a pending CEO Decision and one untouched in
    the Backlog. This exercises every branch of `resume_after_decision`
    on every `make seed` run and leaves an immediate, no-setup CEO
    Decision for a live demo to click through.
19. **The root `Makefile` targets a POSIX shell** (bash/WSL/macOS/Linux),
    with one `ifeq ($(OS),Windows_NT)` branch to pick `.venv/Scripts` vs
    `.venv/bin` for the Python interpreter. `make` itself isn't installed
    in this Windows/git-bash sandbox, so `make dev`/`make seed`/`make
    test` were verified by running each target's underlying commands
    directly (`uvicorn app.main:app`, `pnpm --filter @commander/dashboard
    dev`, `pytest`, `tsc --noEmit`, `next build`) rather than through
    `make` itself.
20. **Verified the full Definition of Done live**, not just via seeded
    data: with the seeded API + dashboard running, created a new mission
    over the real HTTP API, watched it move
    created → assigned → in_progress → in_review → pending_approval in a
    few seconds (mock provider, no API key), approved the resulting CEO
    Decision, confirmed the mission reached `completed`, and confirmed
    both the Timeline (`GET /api/projects/{id}/events`) and a live
    Headquarters page (via headless Chromium) showed the new events with
    zero console errors.

(Further entries appended as later phases land.)

## Sprint 4 — "Real Intelligence"

Judgment calls made while hardening the provider path and adding cost,
model-management, and reporting levers for the CEO. Mock mode must keep
working with zero API keys throughout — see the brief's out-of-scope list.

### Phase 1 — Provider Hardening

21. **`stream()`'s usage is reported through a caller-supplied mutable
    `dict`, not a stateful attribute on the provider instance.** The
    brief fixes the return type to `AsyncIterator[str]`, and a single
    `RoutedProviderGateway` instance can stream several missions
    concurrently (PM/Engineer/Reviewer each get their own gateway call
    within one pipeline run, and multiple missions can be in flight at
    once), so there's no safe place on `self` to stash per-call usage.
    Callers pass `usage: dict[str, int] = {}` into `stream(...)`; the
    provider mutates it in place once it knows input/output tokens. This
    also matches Anthropic's real SSE protocol, which reports
    `input_tokens` in `message_start` and `output_tokens` in
    `message_delta` — i.e. mid-stream, not after — so a "return usage at
    the end" design would have thrown that information away.
22. **Retry-with-backoff lives in `RoutedProviderGateway`, not in each
    concrete provider.** Every call already routes through it to resolve
    the logical model ref, so wrapping `complete`/`stream` there gives
    both `MockProvider` and `AnthropicProvider` the same resilience for
    free instead of duplicating retry logic per provider. Retryable:
    `httpx.HTTPStatusError` with status in `{429, 500, 502, 503, 504}` or
    any `httpx.RequestError` (timeout/connection failure). Everything
    else (4xx other than 429, the `RuntimeError` for a missing API key)
    fails immediately — retrying a bad request or a config error would
    just burn the retry budget on something that can't succeed.
23. **A streaming call is only retried if it fails before yielding its
    first chunk.** Once text has already reached the caller (and, for
    Meetings/missions, already been pushed to the UI as transient
    deltas), retrying from scratch would duplicate output the CEO has
    already seen. This means a mid-stream disconnect still surfaces as a
    hard failure (existing `TaskFailed` path) rather than a silent retry
    — an accepted narrowing of the "max 2 retries" requirement, logged
    here since the brief didn't distinguish pre- vs mid-stream failures.
24. **Backoff is `0.5 * 2^(attempt-1) + jitter` (sub-second to ~1s), not an
    industrial-scale backoff curve.** Commander is a local, single-CEO
    tool, not a high-QPS service fronting shared infra — keeping retries
    fast preserves the live-demo feel (the CEO watching a mission
    complete in seconds) while still being genuinely exponential for the
    rare transient failure.
25. **Retries are observable: every retry publishes `provider.retried`**
    (`{provider, attempt}`, `reason` = exception type/message) through
    the *normal* (persisted) `EventBus.publish`, so a retried call shows
    up in the Timeline — required by Rule 3 (every agent action carries
    a reason) and Design Principle 3 (nothing happens silently).
26. **Added `EventBus.publish_transient()` to the abstract interface, not
    just the concrete `InProcessEventBus`.** Streaming emits one event
    per word/token; persisting every fragment to the `events` table
    would flood it with no corresponding value (only the final,
    persisted `conversation.message` matters for the Timeline, Meeting
    history, and audit trail). Unlike `recent`/`page`/`conversation_for`
    (Sprint 3 concrete-only extensions used solely by the realtime SSE
    route), "publish without persisting" is a capability any future
    EventBus implementation — including a broker-backed one — should
    reasonably support the same way, so it belongs on the port, not just
    today's implementation. `publish_transient` skips both DB persistence
    and module subscriber fan-out (no domain module needs to react to a
    single token), pushing straight to live SSE queues only.
27. **New `EventType.CONVERSATION_MESSAGE_DELTA`** (`kind: "conversation"`,
    never persisted — pushed only via `publish_transient`) carries
    `{text, agent_id, task_id, done}`; a final chunk with `done: true` and
    empty `text` tells the frontend the reply is complete. Both
    `workflow_engine._run_role` (mission pipeline) and
    `tasks.service.post_message` (Meeting replies) now stream: they emit
    one transient delta per chunk, then publish the *same* persisted
    `conversation.message` they always did once the full text is
    assembled — the persisted Timeline/Meeting history is byte-for-byte
    unchanged in shape, only the live UX changed.
28. **Frontend: `RealtimeProvider` intercepts delta events itself** —
    they're never added to the persisted-event rolling buffer and never
    trigger `invalidateForEvent` (a per-token query refetch would be
    wasteful and the DB has nothing new to fetch anyway). It exposes a
    separate `useStreamingReply(taskId)` context that `ChatThread` renders
    as a transient bubble with a blinking-cursor caret. On the `done`
    delta the bubble is cleared after a 400ms delay rather than
    immediately, giving the persisted `conversation.message`'s query
    invalidation time to round-trip so the real bubble replaces the
    streaming one without a flash of "message disappeared" in between.
29. **Bumped two pacing-sleep-dependent timeouts** —
    `tests/test_approval_flow.py`'s `_wait_for_state` (15s → 30s) and
    `scripts/seed.py`'s `wait_for_state` (20s → 35s). The per-role
    pipeline already had four random 0.5-1.5s pacing sleeps across three
    roles (worst case ~18s) before this sprint; adding the mock
    provider's per-word streaming delay (~0.015s/word) pushed a couple of
    tests past the old 15s bound intermittently. Verified the full
    26-test suite green after the bump (see Phase 5 for the final count).

### Phase 2 — Cost & Payroll

30. **New `costs` module, not folded into `provider_gateway`.** The brief
    left the location as a judgment call. `provider_gateway` resolves
    models and makes calls; it shouldn't also own pricing math, DB
    persistence, and per-Company/per-Mission summarization — that's a
    distinct read/report concern with its own schema and API surface, so
    it gets its own module (`app/modules/costs/`) following the same
    shape as every other module (`service.py` + `routes.py` +
    `schemas.py`). It never publishes to the Event Bus and no other
    module reads `CostEntryORM` directly.
31. **Cost recording does not emit a Timeline event.** A `CostEntryORM`
    row is derived telemetry (tokens × a static price), not a CEO-facing
    milestone like a mission moving state or a Decision being made — an
    event per provider call would be exactly the same "flood the
    Timeline with no narrative value" problem Decision 26 avoided for
    streaming deltas. Payroll is instead queried on demand
    (`GET /api/projects/{id}/costs`, `GET /api/tasks/{id}/costs`) and
    polled by the dashboard.
32. **Mock models get nonzero "play money" prices in
    `PRICE_PER_MILLION_TOKENS`** (`model_registry.py`) instead of pricing
    at $0. The sprint's Definition of Done requires "Payroll updated on
    Headquarters" to be observable with `make dev` in mock mode and zero
    API keys — a real DoD check, not just a nice-to-have — so mock roles
    are priced at illustrative-but-plausible rates (planner/reviewer
    ≈ Haiku-tier, builder ≈ Sonnet-tier) purely so the UI has something
    real to show. Anthropic prices in the same table are ballpark public
    figures for the two concrete models in the registry. Unknown models
    price at $0 rather than raising (`cost_for` falls back to `(0.0,
    0.0)`) — a missing price-table entry should never fail a mission.
33. **Payroll (Headquarters vital) is scoped to the current calendar
    month; Mission Budget spent (mission detail) is all-time for that
    mission.** These read like the same metric but answer different
    questions: Payroll is a recurring "what am I spending on this
    Department" number that should reset like a real payroll cycle,
    while a Mission's cost is bounded by its own lifecycle (usually
    minutes to hours) and reporting "this month's spend on this mission"
    would just be a confusing no-op distinction in practice. Employee
    card spend uses the same this-month window as Payroll, since it's a
    breakdown of that same number, not a separate metric.
34. **`record_usage` is called from two call sites with duplicated
    plumbing** (`workflow_engine._run_role`'s callers, and
    `tasks.service.post_message`) rather than centralizing inside
    `RoutedProviderGateway.stream`/`complete`. The gateway's usage dict
    only carries token counts — it doesn't know the `task_id`/`agent_id`/
    `role` a given call belongs to, and threading those through the
    `ProviderGateway` interface would leak workflow concerns into a port
    that Phase 1 deliberately kept as "resolve model, make call, report
    tokens." Both call sites already had every field `record_usage`
    needs in scope, so the small duplication was cheaper than widening
    the interface.
35. **No DB migration tooling added for the new `cost_entries` table** —
    consistent with the accepted MVP tradeoff of no migrations
    (`Base.metadata.create_all` on a fresh/seeded local SQLite file).
    Table added straight to `db_models.py` like every other table so
    far.
36. **Frontend formats Payroll/Mission Budget/Employee spend with a
    precision-aware `formatUsd()` (4 decimals below a cent, 2 above)
    instead of a flat `toFixed(2)`.** Caught live in Playwright
    verification: one mock mission's total cost is ~$0.0012 (a handful
    of hundred-token calls against per-million-token prices), which
    rounds to "$0.00" everywhere with two decimals — Payroll would look
    frozen at zero after every mission in mock mode, failing the "Payroll
    updated on Headquarters" Definition-of-Done check even though the
    underlying number is accruing correctly. Fixing the display (rather
    than inflating mock prices just to make the UI look good) keeps the
    price table honest and still makes the change visible to the CEO.

### Phase 3 — Model Management

37. **Mock's `options_for_role` offers no real choice — only its own
    recommended model per role.** `MockProvider._role_from_ref` infers
    what shape of text to fabricate by substring-matching the *concrete*
    model id ("planner" / "builder" / else reviewer). If the CEO could
    reassign, say, `mock-planner-v1` onto the Reviewer role, the Reviewer
    would silently start emitting planner-shaped prose with no
    `**Verdict:**` line, breaking `workflow_engine`'s outcome parsing
    without ever raising an error — a correctness bug, not a UX
    limitation. Anthropic's models are general-purpose, so any of them is
    valid for any role there; only mock is restricted. This keeps rule 6
    ("must fully work with `COMMANDER_PROVIDER=mock`") intact while still
    giving the CEO a real lever wherever it's actually safe to pull.
38. **Model overrides persist in the existing `settings_kv` table**, keyed
    `model_override:{project_id}:{role}`, the same mechanism Company
    Settings already uses for secrets (`secret:{name}`). One CEO-editable
    string per (project, role) doesn't justify a new table or a schema
    migration — this repo has none (Decision 35) — and the key-prefix
    convention was already established.
39. **The API's `role` vocabulary stays `planner`/`builder`/`reviewer`**
    (the model_registry's logical-ref vocabulary), matching the brief's
    own instruction that the endpoint operates on "role
    (planner/builder/reviewer)". The brief's own example Timeline text
    ("CEO reassigned Engineer to claude-sonnet-4-6") uses the
    agent-facing name instead, so `model_registry/service.py` translates
    via a small `_ROLE_LABEL` dict (`planner`→PM, `builder`→Engineer,
    `reviewer`→Reviewer) only when building the human-readable `reason`
    string — the payload's `role` field itself stays in registry
    vocabulary for API/event consumers.
40. **`ModelChangedPayload` (an unused Sprint 3 skeleton event type) is
    extended with a `role` field and, for the first time, actually
    published** — by `model_registry.service.set_role_model`, only when
    the override actually changes the effective model (a no-op re-save of
    the already-active model emits nothing, mirroring how other
    state-change events in this codebase skip no-op transitions).
41. **`ProviderGateway` gains a concrete (non-abstract) `resolve_model()`
    method on the base interface, defaulting to identity** (`return
    model_ref`), overridden only by `RoutedProviderGateway` to do real
    logical-ref-to-override-aware-concrete-model resolution. Making it
    abstract would have forced trivial overrides onto `MockProvider`/
    `AnthropicProvider`, which only ever receive an already-resolved
    concrete model id from the router in front of them — the identity
    default is the semantically correct behavior for them, not a stub.
    This is what lets `workflow_engine`/`tasks.service` ask the gateway
    "what model did you actually just use" for cost logging, so a CEO
    override is reflected in Payroll instead of silently cost-logging the
    registry default.

### Phase 4 — CEO Daily Report

42. **The report window is a fixed trailing 24h (`now - 24h` to `now`),
    not the prior calendar day.** The brief asks for "the prior 24h"
    explicitly, and a fixed window is simpler to reason about and test
    than a calendar-day boundary that would depend on the CEO's timezone
    (which this MVP has no concept of — everything is stored/compared in
    UTC). Generating a report at any time of day always summarizes
    exactly what the CEO missed since roughly this time yesterday.
43. **`reporter-default` is added to `model_registry.MODEL_REGISTRY` but
    deliberately left out of `ROLES`/`options_for_role`.** Decision 39's
    CEO-facing model-reassignment lever only makes sense for roles the
    CEO actually manages (PM/Engineer/Reviewer) — the report-writer isn't
    an Employee with a Timeline presence, and letting the CEO swap it
    would risk the same mock-mode role/template mismatch Decision 37
    already ruled out for the three real roles, for a feature (report
    tone) that isn't part of this sprint's brief.
44. **Mock mode gets a dedicated `"reporter"` template branch in
    `mock_provider.py`**, following the same `_role_from_ref`
    substring-dispatch pattern used for planner/builder/reviewer
    (Decision 37), rather than reusing one of the existing three. The
    report's shape (missions/decisions/highlights/payroll → prose) is
    structurally different from a mission-pipeline reply, so it gets its
    own deterministic template fed by the same structured `opts` kwargs
    the gateway already threads through `complete()`.
45. **Added `costs.summary_since(session_factory, project_id, since)` as a
    third, distinct cost-summary shape**, alongside Decision 33's
    calendar-month `summary_for_project` (Payroll) and all-time
    `summary_for_task` (Mission Budget). The Daily Report needs "spend in
    the last 24h," which is neither of the other two windows — forcing
    it through the calendar-month function would double-count or
    under-count depending on where midnight-of-the-month falls relative
    to the report's 24h window, so a third, explicitly-windowed query was
    cheaper and clearer than overloading an existing one with an optional
    date-range parameter.
46. **Report generation itself is not cost-logged against any Employee.**
    `record_usage` (Decision 34) requires a `task_id`/`agent_id`/`role`
    the call belongs to; the report-writer has none of those — it's a
    one-off CEO-triggered summary, not an Employee action — so its token
    cost is left out of Payroll rather than inventing a synthetic
    "reporter" agent/task just to satisfy the existing plumbing.
47. **No DB migration for the new `reports` table** — same accepted
    tradeoff as every other table in this codebase (Decision 35):
    `ReportORM` added straight to `db_models.py`, picked up by
    `Base.metadata.create_all` on next boot.

### Phase 5 — Verification & docs sync

48. **`docs/ARCHITECTURE.md`'s module table and Frontend section had
    drifted since Sprint 4 Phase 2** — the `costs` module was never added
    as a row, `model_registry`'s description still read "Static map" after
    Phase 3 added CEO overrides, and Frontend bullets didn't mention
    Payroll, streaming replies, or model reassignment. Caught and fixed
    during this phase's doc-sync pass rather than earlier, since Phases
    1-3 each ended with a commit but not a full doc re-read — worth noting
    here since the Doc Sync Rule expects updates in the *same* commit as
    the change; this sprint corrects it retroactively in one pass instead.
    Full backend suite (42 tests) and dashboard `tsc --noEmit` + `next
    build` verified green, then the Daily Report card and detail page
    verified in a real headless browser (Playwright, scratch install per
    Decision 16) against the live seeded company: generate → card updates
    → view full report → past-reports list on a second generate, zero
    console/page errors.

### Sprint 4.5 — Employee Profiles

49. **`AgentProfile.model_config` sets `protected_namespaces=()`.** Pydantic
    v2 warns on any field prefixed `model_` (it reserves that namespace for
    its own `model_*` methods). `model_ref` is the correct, spec-mandated
    field name (mirrors `RoutedProviderGateway.resolve_model`'s
    `model_ref` parameter throughout the provider path) — silencing the
    warning was the right call over renaming the field to dodge it.
50. **Default founding profiles use `AgentProfile`'s own field defaults
    per role, not per-role trait variation.** The old `DEPARTMENT_ROSTER`
    persona strings gave PM/Engineer/Reviewer distinct baked-in voices;
    the brief's model replaces that with a CEO-editable `AgentProfile`
    instead. Rather than pre-seed three different personality/working/
    decision-style combinations (an arbitrary design choice with no spec
    backing), founding profiles start at the schema defaults
    (`professional` / `balanced` / `balanced`) for every role, and the
    role's distinct voice now comes entirely from `ROLE_CONTRACTS` in
    `prompt_builder`, not the profile. CEOs differentiate Employees by
    editing profiles after founding, which is the point of the sprint.
51. **`/api/agents/{agent_id}/profile` has no `project_id` prefix.**
    Mirrors the existing direct-resource convention (`/api/tasks/{task_id}`,
    `/api/approvals/{approval_id}`) rather than nesting under
    `/api/projects/{project_id}/agents/{agent_id}/profile` — `agent_id` is
    already globally unique (UUID PK) and the route handler doesn't need
    `project_id` for anything but the event payload, which it reads off
    the loaded `AgentORM` row instead.
52. **`agent_override` is an explicit keyword-only parameter on
    `resolve_model`/`complete`/`stream`, never smuggled through `**opts`.**
    `**opts` already carries provider-specific/mock-flavor context
    (`task_title`, `context`, etc.) that flows through to the underlying
    provider; `agent_override` is consumed entirely by
    `RoutedProviderGateway` for model resolution and must never reach
    `MockProvider`/`AnthropicProvider`, which only ever see an
    already-resolved concrete model id. An explicit parameter makes that
    boundary a type signature, not a convention callers have to remember.
53. **Phases 1, 2, and the runtime-wiring half of Phase 4 were implemented
    in one continuous pass before running any tests**, rather than testing
    after each phase as the PROGRESS checklist's phase boundaries might
    imply. Renaming `AgentORM.persona` -> `profile` (Phase 1) transiently
    breaks every runtime call site (`workflow_engine.py`,
    `tasks/service.py`) until Phase 4 rewires them to build prompts via
    `prompt_builder` — there is no good intermediate state to pause and
    test at. Accepted because the CEO explicitly asked for continuous
    autonomous work through to the Phase 6 Definition of Done rather than
    phase-by-phase verification; the full suite (42/42) was run once all
    four phases' code was in place and passed clean on the first attempt.
54. **`MockProvider`'s personality flavor (item 4.3) is never appended to
    Reviewer output.** The Reviewer's trailing `**Verdict:** ...` line is a
    hard parsing contract (`workflow_engine` reads it verbatim, and
    `test_mock_provider.py` asserts the *last line* is exactly one of the
    two allowed strings) — appending flavor text after it would silently
    break mock-mode approvals. Planner and Builder output get a
    one-sentence suffix sniffed from trait keywords in the system prompt
    (e.g. `"risk-aware"` -> a precaution note); Reviewer output is left
    untouched. This is also the only visible sign, in mock mode, that a
    CEO's profile edit changed anything, since MockProvider doesn't
    actually read the system prompt for content.
55. **The Employee profile save flow (item 5.5) uses the Settings page's
    inline "Saved." text pattern, not a toast**, even though the brief's
    wording says "toast." No toast library exists anywhere in the
    dashboard (checked before starting Phase 5) and Company Settings
    already established this exact save-confirmation pattern
    (`useState` boolean + inline green text next to the button) — adding
    a toast dependency for one more save button would be inconsistent
    with the rest of the app and unnecessary scope for this sprint.
56. **The Employee profile page shows the effective model as
    role-plain-name text (e.g. "PM · claude-...") in the header, and the
    "Use company default" select option is labeled with the current
    company default model**, rather than a separate always-visible
    "current model" field. This satisfies item 5.2 ("model plain name")
    without duplicating the Company Settings page's per-role model
    table — the CEO sees the effective model right where they'd change
    the override, not in a second place that could drift out of sync.

### Sprint 4.7 — Headquarters UX

57. **The template (§10.6) centralizes role *identity* — key, founding
    name, avatar color, model ref, role contract, default profile,
    intro line — not the pipeline's *shape*.** `workflow_engine.py` still
    hardcodes a 3-step PM -> Engineer -> Reviewer sequence of awaits;
    only the literal `"pm"`/`"engineer"`/`"reviewer"` strings and
    `"planner-default"`/`"builder-default"`/`"reviewer-default"` refs
    inside it were replaced with `TEMPLATE.roles` lookups. A fully
    data-driven pipeline (N roles, engine loops over `TEMPLATE.roles`)
    is out of scope for a sprint whose brief only asks for one template
    (`software_company`) and explicitly bars adding speculative
    multi-template machinery — item 1.4 ("no hardcoded role-name
    branching outside template") is satisfied because no code outside
    `app/templates/` tests role identity by string comparison anymore,
    not because the pipeline itself is generic.
58. **The Situation Report is ephemeral, not cached or event-sourced.**
    `GET /projects/{id}/situation` calls the provider fresh on every
    request and wraps the call in try/except, falling back to a cheap
    deterministic sentence built from DB facts (`_fallback_text`) on any
    provider error or timeout. A cached/scheduled version would need a
    new table, a refresh trigger, and staleness handling — none of which
    the brief asks for — and a dashboard read must never 500 or hang
    just because the CEO hasn't configured a real API key. Mock mode and
    real-provider mode both degrade to the same fallback path on error,
    so the endpoint can't break CLAUDE.md's "must fully work with
    `COMMANDER_PROVIDER=mock`" rule.
59. **`InvalidModelRefError` subclasses `ValueError` instead of being a
    new sibling exception.** `agent_profiles.update_profile` already
    raises bare `ValueError` for "unknown agent" (Sprint 4.5,
    `test_update_profile_unknown_agent_raises`), and `routes.py` mapped
    every `ValueError` to a 404. A model-ref validation failure is a 422
    (bad request body), not a 404 (missing resource), but changing the
    404 test's exception type would break an existing, still-correct
    test. Subclassing keeps `except ValueError` callers (including the
    old test) working unchanged while giving `routes.py` a strictly
    narrower `except InvalidModelRefError` branch it can catch *first*
    and map to 422.
60. **`ApprovalORM` gained `reviewer_agent_id`, `reviewer_name`,
    `sections`, and `raw_summary` columns, captured at approval-creation
    time in `workflow_engine.py` rather than derived later via a join.**
    The Decisions page (Phase 3) needs reviewer attribution and the
    parsed Problem/Recommendation/Risk/Impact sections on every
    `ApprovalResponse`; the reviewer identity and full audit text are
    already in scope at the moment the workflow engine creates the
    `ApprovalORM` row (it just finished awaiting the Reviewer's
    response), so writing them once at creation is simpler and cheaper
    than joining `AgentORM` and re-parsing `raw_summary` on every read.
    No migration was needed — no `commander.db` exists yet in this repo
    checkout, so `create_all` picks up the new columns on next boot.
61. **`parse_decision_sections` bounds each section's capture group with
    a paragraph-break lookahead (`(?=\n\s*\n|\Z)`) instead of splitting
    on the next known label or `**Verdict:**`.** A naive "capture until
    the next label" regex let the last section (Impact) swallow the
    trailing markdown checklist that sits between it and the Verdict
    line, producing a garbled multi-paragraph value — caught by manual
    live E2E verification (`TestClient`, real pipeline run), not by unit
    tests, since the section-parsing tests were written after the fix.
    Bounding on the next blank line instead of a label match is also
    provider-robust: a real LLM's prose is not guaranteed to always emit
    every label, but paragraph breaks between sections are a much safer
    assumption than exhaustive label enumeration.
62. **`GET /api/approvals/history` reuses the existing `list_all` service
    function rather than a new query.** `approvals/service.py` already
    had an unused-by-routes `list_all(session_factory, project_id)` that
    returns every approval for a project ordered by creation time —
    exactly what the Decisions page's History tab (item 3.4) needs. Adding
    the route was a one-line wiring change, not new service logic.
63. **The status vocabulary is split: backend owns *which token* an
    internal state maps to, frontend owns *what the token says*.**
    `app/core/contracts.py` adds a `StatusWord` enum plus
    `TASK_STATE_STATUS_WORD`/`AGENT_STATE_STATUS_WORD` dicts and regenerates
    them into `packages/event-schemas/ts` as real TS consts (extended
    `generate_ts_schemas.py` with `emit_status_word_map`, since the
    existing generator only knew how to emit enums and Pydantic model
    interfaces, not arbitrary dict constants). The dashboard's
    `components/StatusWord.tsx` then owns `STATUS_WORD_LABEL`/
    `STATUS_WORD_TONE` — the copy and color are UI concerns the backend
    has no reason to know about, but *which* internal states collapse to
    the same external word is a domain fact that belongs with the state
    machines. This keeps "one source of truth" (brief's own wording) for
    the mapping while leaving room for i18n to be a frontend-only change
    later — a second locale map, not a second mapping.
64. **`StatusWord` carries two tokens beyond UX_SPEC §1's seven-row
    table: `CANCELLED` and `IDLE`.** The spec's vocabulary table doesn't
    address `TaskState.CANCELLED` (a CEO-initiated terminal state,
    distinct from `FAILED` — nothing went wrong) or `AgentState.IDLE` (an
    Employee with no current Mission, the common/default state, not
    internal jargon needing translation). Omitting them would leave two
    real states with no external word at all. Both get plain,
    unsurprising copy ("Cancelled", "Idle") rather than forcing them into
    an existing token that would misdescribe them.
65. **`TaskState.ASSIGNED` and `AgentState.ASSIGNED` map to `PLANNING`,
    and `TaskState.RETRYING` maps to `DEVELOPING`, not a new/different
    token.** `assigned` is the transient instant between task creation
    and the workflow engine picking it up — from the CEO's perspective
    nothing is happening yet, so it reads the same as "not started."
    `retrying` is the engine's own backoff-and-retry-once machinery
    (Sprint 3/4 decision, see entry on retry-with-backoff) recovering
    from a transient provider error automatically; surfacing it as
    "Blocked" would incorrectly imply the CEO needs to act, when the
    system is already handling it and will settle back into `DEVELOPING`
    or fail outright.
66. **The Missions kanban (`missions/page.tsx`) now buckets columns by
    `StatusWord` token via `taskStatusWord()`, not a hand-maintained list
    of raw `TaskState` strings**, and its "In Progress"/"Needs CEO
    Decision" column labels were renamed to the spec's exact copy
    ("Developing"/"Needs your decision"). This was flagged during the
    Phase 2 audit as an independent, fifth status-mapping site in the
    dashboard (alongside the two now-deleted `TASK_STATE_LABEL`/
    `AGENT_STATE_LABEL` tables in `lib/utils.ts` and the Headquarters
    active-Missions filter) — collapsing it onto the shared token map
    was the entire point of item 2.3 ("replace every status render
    site"), not just the four `StatusPill` call sites.
67. **`DecisionCard` replaces `ApprovalCard` as a single component with
    two render modes (`isPending`), not two components.** The pending
    (live, actionable) and decided (read-only history) views share the
    same fixed anatomy — Problem / Recommendation-with-reviewer /
    Risk / Impact — and differ only in the footer (action buttons vs.
    comment + outcome text). A `hasSections` check falls back to raw
    `approval.raw_summary` when the lenient parser (Phase 1, item 1.6)
    extracted nothing, so old/unparseable audits never render blank
    space. This one component now serves three placements: the Decisions
    page (both tabs), Headquarters' pending strip, and Mission Detail —
    per the brief's "one anatomy, two placements" framing, now three.
68. **Reviewer avatar color is resolved by each caller, not carried on
    `Approval` itself.** `ApprovalResponse`/`Approval` only has
    `reviewer_agent_id`/`reviewer_name` (Phase 1 additions) — no color,
    since avatar color lives on the Employee record, not the approval.
    Each of the three call sites already fetches the company's Employees
    list for its own purposes, so each builds an `employeeById` lookup
    map and passes `reviewerColor` down as an optional prop; `DecisionCard`
    defaults to a neutral slate (`#64748b`) if the lookup misses (e.g.
    reviewer_agent_id is null on very old approvals).
69. **`GET /api/approvals/history` is consumed by a new `useApprovalHistory`
    hook, kept fully separate from `useApprovals` (pending-only) rather
    than one hook with a status filter param.** The Decisions page's two
    tabs have different loading/empty-state copy and the History tab
    additionally derives `outcome` text from the Mission's terminal state
    (`resume_after_decision`'s approve→COMPLETED / reject→CANCELLED /
    request_changes→IN_PROGRESS mapping) — keeping the queries and their
    cache keys (`keys.approvals` vs `keys.approvalHistory`) independent
    avoids one hook's return shape needing to serve two different
    consumers.
70. **Sidebar gets a "Decisions" link positioned directly after
    "Headquarters"**, ahead of "Missions"/"Employees"/"Company Settings" —
    matching the brief's target nav order and reflecting that CEO
    Decisions are meant to be a first-class, frequently-visited surface,
    not something only reachable by drilling into a Mission.
71. **`EventBus.page()`'s cursor direction was flipped from oldest-first
    to newest-first — a bug fix surfaced by building the Timeline page,
    not a Phase 4 feature in its own right.** The old contract (`cursor`
    = last-seen `seq`, `seq > cursor`, ascending) meant the *first* page
    of any company's Timeline was always its oldest 50 events — for any
    company with meaningful history, opening the Timeline showed ancient
    activity, not current. Headquarters' condensed feed only avoided this
    by fully replacing the historical query with the session's live SSE
    buffer the instant one event arrived, which just hid the bug rather
    than fixing it (and showed nothing-recent on a fresh page load with
    no new events yet). The new contract (`cursor` = lowest `seq` seen,
    `seq < cursor`, descending) makes `cursor=None` always mean "the most
    recent page" and turns "load earlier" into a direct forward call
    chain — the exact semantics the brief's "Cursor pagination for
    history (load earlier)" describes. `next_cursor`'s "always return if
    `rows` is non-empty" behavior (even on a short final page) is kept
    unchanged from before, so the existing pagination test's assertions
    hold either way; a new assertion on the actual event order was added
    since the old test never pinned it down.
72. **`useTimelineFeed` is a separate `useInfiniteQuery` hook with its
    own cache key (`timelineFeed`), not a reuse of the existing
    `useTimeline`.** Headquarters' `useTimeline` wants exactly one page
    (the most recent N events, condensed); the Timeline page wants an
    accumulating, paginated list. Sharing one cache key between a
    single-object query and a multi-page infinite query would mean each
    hook occasionally reads a cache entry shaped for the other. Both keys
    are invalidated together in `invalidateForEvent` on every SSE event,
    so an open Timeline page stays live by refetching its already-loaded
    pages (React Query's default infinite-query invalidation behavior) —
    reusing the app's existing "SSE event -> invalidate -> refetch"
    convention rather than building a bespoke live-merge path for this
    page. Trade-off accepted: if new events push the boundary of an
    already-fetched page while the CEO is mid-session, a handful of
    events at that exact seam can go temporarily unlisted until "Load
    earlier" is clicked — acceptable at this MVP's event volume, not
    worth a windowed/merge-aware pagination scheme.
73. **The CEO/Technical hidden set (`MECHANISM_EVENT_TYPES` in
    `lib/timelineVocabulary.ts`) is `TASK_STATE_CHANGED`,
    `AGENT_STATE_CHANGED`, `PROVIDER_RETRIED`, `SYSTEM_HEARTBEAT`, and
    `WORKSPACE_FILE_CHANGED`.** Each mirrors a state transition or retry
    mechanism that's already narrated elsewhere by a more meaningful
    event (e.g. `TASK_STARTED`/`REVIEW_STARTED`/`TASK_COMPLETED` cover
    the same moments `TASK_STATE_CHANGED` fires for) or is pure plumbing
    a CEO never needs to act on. `MODEL_CHANGED` was deliberately **not**
    included even though the brief's example phrase says "model
    resolution" — `MODEL_CHANGED` only fires when the CEO themselves
    reassigns a per-role model from Company Settings, so hiding it would
    hide the CEO's own action from their own Timeline. The same set
    doubles as the digest-grouping predicate (`groupForDigest`) — one
    definition of "minor," not a second list to keep in sync.
74. **Digest grouping only activates in Technical view.** CEO view
    already filters `MECHANISM_EVENT_TYPES` out of the feed entirely
    (Phase 4 hidden-set behavior), so by the time a Technical-view-only
    digest pass would run there's nothing minor left to group — the two
    features are complementary, not overlapping: CEO view hides the
    noise, Technical view shows it but keeps it compact.
75. **`TimelineFeed`'s default (`technical` prop omitted) now filters
    mechanism events, changing Headquarters' condensed feed's existing
    behavior, not just adding a new page.** `TimelineFeed` is the ★-rated
    shared component (UX_SPEC §5) — upgrading it once for both call sites
    was preferred over forking a page-only variant, and CEO view as the
    default matches Headquarters' "condensed" framing (§3.2) better than
    the previous unfiltered dump of every internal state-change event.
76. **`companyStatusWord()` (`components/StatusWord.tsx`) reduces a
    company's Mission states to one token via a fixed most-urgent-first
    priority list** (`NEEDS_DECISION > BLOCKED > REVIEWING > DEVELOPING >
    PLANNING`, falling back to `IDLE` for an all-terminal/no-Missions
    company). A company card can't show every Mission's status, and
    silently picking "whatever the last Mission happens to be" would let
    a stuck or CEO-waiting Mission hide behind an unrelated one that's
    quietly `PLANNING`. Priority-by-urgency means the card can never
    under-report how much the CEO's attention is needed.
77. **"Risks open" (Headquarters Vitals) is implemented as a count of
    Missions in the `FAILED` StatusWord state, not a dedicated Risk/Issue
    entity.** Grep-confirmed: no `risks`/`issues` module exists anywhere
    under `apps/api/app/modules`, and `EventType.BUG_FOUND` is defined in
    the event schema but never emitted by any workflow. CLAUDE.md's
    terminology table maps internal "Issue" to UI "Risk" but nothing in
    the codebase currently tracks that entity. Building a full Risk
    module is out of scope for a UX-focused sprint brief, so FAILED
    Missions — the closest existing signal that something needs the
    CEO's attention — stand in as the proxy. Revisit if/when a real
    Risk/Issue module ships; this is a placeholder, not a permanent
    modeling decision.
78. **Headquarters' four Vitals cards are wrapped in `Link`s that reuse
    existing pages** (Missions active -> `/missions`, Employees working
    now -> `/employees`, Risks open -> `/missions`, Payroll this month ->
    `/employees`) **rather than each getting a bespoke destination.**
    `/missions` already supports filtering by Mission state visually via
    its kanban columns, and `/employees` already renders per-Employee
    spend (`spendByAgent` from `useCompanyCosts`), so both Payroll and
    Risks land on a page that already answers the "why" behind the
    number without new routes. "Employees working now" also changed from
    a raw headcount to `agentStatusWord(state) !== IDLE` count, matching
    what the linked `/employees` page actually highlights (who's active
    right now, not company size).
79. **`CompanyCard` is a self-fetching component** (its own
    `useEmployees`/`useMissions`/`useApprovals`/`useTimeline` calls per
    company, same N+1 pattern as `DecisionCard`/`EmployeeCard`) **rather
    than My Companies fetching everything up front and passing props
    down.** TanStack Query dedupes/caches per company ID regardless of
    which component issues the call, and keeping each card
    self-contained means the My Companies page itself stays a thin list
    — consistent with the precedent already set by every other
    "card that needs its own related data" component in this codebase.
    Accepted as an MVP-scale tradeoff (a CEO with dozens of companies
    would need a dedicated summary endpoint instead).
80. **`DailyReportCard` was deleted and replaced by a dedicated
    `/company/[id]/reports` list page** (mirroring the Decisions page's
    header + list + empty-state shape), with `ReportDetail`'s back-link
    changed from "-> Headquarters" to "-> Reports" and a "Reports" entry
    added to the sidebar between Timeline and Company Settings. The
    brief calls for promoting Reports once it's "only a card" on
    Headquarters — Headquarters now only links out to `/reports` rather
    than embedding report generation/preview inline, keeping the
    Headquarters page focused on the CEO's Decision strip, Situation
    Report, Vitals, and condensed Timeline per UX_SPEC §3.2.
81. **Employee intro lines are posted as task-less conversation events**
    (`ConversationMessagePayload.task_id=None`) **right after `AGENT_CREATED`
    in `DBAgentRuntime.create_department`, not through the Meeting/message
    API.** The payload contract already allowed `task_id: str | None`, so
    no schema change was needed. Task-less means intros show up in the
    company Timeline (where onboarding needs them, §6) but never leak
    into a specific Mission's Meeting transcript, which is exactly the
    boundary the brief draws ("introduce themselves in the Timeline").
    Intros are emitted in template role order (PM, Engineer, Reviewer),
    which is also pipeline order — reads narratively correct once the
    Timeline's newest-first ordering (decision 71) puts them in a
    contiguous block right after founding.
82. **Starter Missions are served from a new `GET
    /api/projects/{id}/starters` endpoint that returns `TEMPLATE.starters`
    directly, with no DB lookup or project-existence check.** The data is
    static and template-owned (§10.4: one template, no picker), so there
    is nothing project-specific to look up — treating it as a per-project
    REST resource (`/projects/{id}/starters`) rather than a global
    `/starters` endpoint was still the right call for consistency with
    every other project-scoped route and to leave room for a future
    template-per-project model without a URL change.
83. **The Missions page's empty state creates the first starter
    (`starters[0]`) directly via `useCreateMission`, not a picker over
    all `TEMPLATE.starters`.** The brief calls for "one starter Mission
    suggestion," singular — `STARTERS` keeps a second entry only so a
    future template swap has more than one to choose from (see the
    template file's own comment), not because today's UI should surface
    a choice.
84. **The My Companies founding form's optional "what it should build"
    field (§3.1) immediately creates a Mission from that text via a
    direct `api.createMission` call, not `useCreateMission`.** It fires
    once, imperatively, inside the same submit handler that creates the
    company and before the CEO ever lands on a page that has that hook
    mounted — using the mutation hook here would mean calling a hook
    conditionally, which breaks the Rules of Hooks. The page the CEO
    lands on (`/company/[id]`) fetches its own fresh Mission list on
    mount, so no manual cache write-back is needed. If left blank, the
    CEO instead sees the Missions page's starter-suggestion empty state
    (decision 83) — both paths reach a live Mission, just via different
    numbers of clicks.
85. **No EmptyState-component pass on Employees, Decisions, Reports, or
    the Meeting transcript.** Employees is founded with the trio and can
    never actually be empty in this template, so an empty state there is
    dead code. Decisions' empty state is intentionally a quiet
    non-actionable line ("Nothing needs your decision.") per the brief's
    own wording — turning it into an "invitation to act" would misrepresent
    a state where there is nothing for the CEO to do. Reports and the
    Meeting transcript already carry inline invitational copy ("Generate
    one to get started.", "Say hello to the Department.") next to their
    existing action affordances, so wrapping them in the `EmptyState`
    component would be a pure refactor with no behavior change — skipped
    per the standing "don't refactor beyond what the task requires" rule.
86. **New Phase 6 backend behavior (founding intro events, `GET
    /starters`) gets one new test file, `tests/test_onboarding.py`,
    reusing the existing `Harness` service-layer pattern rather than
    introducing HTTP test infrastructure.** No test in the suite uses
    `TestClient`/`AsyncClient`; every existing test drives service
    functions directly against the harness fixture. Adding a second
    testing style for two tests wasn't worth the inconsistency. Full
    suite is 75/75 after the addition (was 73 before Sprint 4.7 Phase
    6); Phase 1-5 coverage (template founding parity, section parsing,
    situation endpoint, status mapping, model_ref validation) was
    already satisfied by `test_template.py`, `test_decision_parsing.py`,
    `test_situation.py`, `test_status_vocabulary.py`, and
    `test_agent_profiles.py` — no additional files needed for those.

### Sprint 5 — Workspace

Judgment calls made while giving Employees a real git workspace under the
absolute no-execution gate: workspace_manager is git I/O only, the
pipeline/contract layer is what turns that into CEO-legible summaries.

87. **`WorkspaceManager` is redesigned from Sprint 2's `@final`-wrapped
    template-method ABC into a plain ABC with no `EventBus` dependency,
    matching `core/interfaces/workflow_engine.py`'s shape.** The Sprint 2
    design existed to structurally guarantee an event got published after
    every mutation, by making the public method concrete and routing
    concrete implementations through an abstract `_do_*` hook they
    couldn't bypass. Sprint 5's actual operations don't fit that
    "one hook, one fixed event" template: `write_files` does a validated
    multi-file write with per-file skip semantics (no single event
    describes "12 written, 2 skipped" well), `ensure_initialized` is
    conditional (event only on the branch that actually initialized),
    and `merge` can legitimately fail (the caller needs the exception,
    not a swallowed non-event). Worse, the caller (`workflow_engine`)
    always has the mission context — task id, attempt number, why this
    write is happening — needed to write a good event `reason`, and the
    manager never does. So `workflow_engine` now publishes
    `workspace.initialized` / `code.changed` / `branch.merged` itself,
    right after calling the plain git methods, the same way it already
    publishes `task.*` events around `agent_runtime` calls. Concrete
    `WorkspaceManager` implementations are pure git I/O and are not
    trusted (or able) to touch the event bus.
88. **The old placeholder `EventType.WORKSPACE_FILE_CHANGED` /
    `WORKSPACE_COMMITTED` / `WORKSPACE_BRANCH_CREATED` members (Sprint 1
    stubs, never wired to any real emitter) are replaced outright by
    `WORKSPACE_INITIALIZED` / `CODE_CHANGED` / `BRANCH_MERGED` rather than
    kept alongside the new set.** Nothing published or subscribed to the
    old three — grep confirmed only the enum, the payload-model mapping,
    and one Timeline-vocabulary entry referenced them — so keeping both
    sets would just be dead enum surface with no compatibility to
    preserve. `code.changed` (not `workspace.committed`) is the payload
    that actually carries the file/line stats the ChangeSummaryCard and
    Timeline need, matching the brief's own event list verbatim.
89. **`code.changed` and `branch.merged` are deliberately left out of
    `MECHANISM_EVENT_TYPES` in `timelineVocabulary.ts`.** That set is the
    CEO-view "hide as noise" list (provider retries, heartbeats, raw
    state-changed rows). A code mission's Change Summary landing and its
    merge to main are exactly the kind of CEO-legible milestones the
    Timeline exists to surface, not mechanism to hide — consistent with
    how `task.completed` and `approval.granted` are already left out of
    that set.
90. **The Reviewer's input for a landed code mission is `Change Summary +
    truncated real diff`, replacing the raw deliverable text entirely —
    not appended alongside it.** The Engineer's raw output for a code
    mission is the Change Summary followed by the full file contents in
    FILE blocks; handing that whole blob to the Reviewer as "context"
    would mean the Reviewer's prompt duplicates the file contents twice
    over once a diff is added, and the Reviewer contract already asks it
    to audit against a diff, not a full-file dump. `TaskORM.result_markdown`
    follows the same logic: on a successful commit it stores just the
    Change Summary (what the mission detail page's ChangeSummaryCard
    needs), not the raw FILE-block text — the actual file contents live in
    the git workspace and are reachable via the Workspace page/diff
    endpoints (Phase 4), never duplicated into a DB text column.
91. **Mission branches are named `mission/{task_id[:8]}`, computed once
    and reused across every attempt (request-changes retries recommit to
    the same branch; `TaskORM.branch_name` is the source of truth once
    set).** This matches `create_branch`'s already-idempotent contract
    (Phase 1) and is what makes "Request changes -> same-branch recommit"
    a no-op change to the retry path: `_run_pipeline` already re-fetches
    the task fresh from the DB on every attempt, so `task.branch_name`
    naturally carries forward.
92. **A merge conflict on approve leaves the Approval marked `approved`
    (the CEO's decision stands) while the Task moves to `BLOCKED`, not
    `rejected`/`cancelled`.** These are orthogonal facts: the CEO approved
    the deliverable on its merits; the technical failure to land it on
    main is a separate, human-actionable problem (someone edited main out
    of band) that the CEO didn't decide and shouldn't have attributed to
    them as a rejection. The pending-approval-mutation logic was pulled
    out of `_finish_task` into a shared `_mark_pending_approval(task_id,
    status, comment)` helper so both the normal complete/cancel path
    (`_finish_task`) and the new merge-failure path
    (`_block_task_on_merge_failure`) can each pick the right `status`
    independently rather than one deriving it from the other's target
    `TaskState`. No auto-resolution is attempted on the conflict itself,
    per the brief.
93. **Per-file diff stats (Expansion 1) are parsed client-side from the
    existing `GET /tasks/{id}/diff` response rather than adding a
    per-file-stat backend endpoint.** `CommitResult`/`code_stats` only
    carry aggregate counts (files_added/modified/deleted, additions,
    deletions summed across the commit); a real per-file breakdown only
    exists in the unified diff text itself. Since `diff()` already returns
    that text, `lib/utils.ts`'s `parseUnifiedDiff` slices it on
    `diff --git` boundaries and counts +/- lines per file — no new git
    plumbing, no new response shape, and the diff stays lazy-loaded (only
    fetched when the CEO expands "View file changes", never on the
    landing view, per item 4.5).
94. **The task-scoped diff endpoint lives in `tasks/routes.py` /
    `tasks/service.py`, not `workspace_manager/routes.py`.** `diff()`
    needs a `branch_name`, which only `TaskORM` knows (per-mission);
    `list_tree`/`read_file`/`recent_merges` are project-wide against a
    `ref` (default `"main"`) and have no task context, so they live in the
    new `workspace_manager` module instead. Both modules resolve "does
    this company exist" by querying `ProjectORM` directly in their own
    `service.py` (mirroring `reports`/`situation`), rather than importing
    each other's service functions, per the "modules never import each
    other's internals" rule.

## Sprint 6 — "Execution Sandbox"

95. **`CheckSpec` (the trusted, template-defined "name + detect_globs +
    command" tuple) lives in `core/interfaces/sandbox.py`, next to
    `CheckResult`/`SandboxRunner`, not in `templates/software_company.py`.**
    It's genuinely the sandbox port's input shape — the same category as
    `CheckResult` — not template-specific data; `software_company` just
    supplies a value of that shape (`TEMPLATE.checks`). Putting it in
    `core/interfaces` keeps the dependency direction unchanged
    (`templates/` -> `core/` only, matching the existing `AgentProfile`
    import) instead of making `templates/` reach into `modules/`.
96. **Execution-enabled is a per-project `settings_kv` toggle
    (`execution_enabled:{project_id}`), defaulting to `True` when the row
    has never been set.** Mirrors the existing generic `SettingORM`
    key-value pattern (no new table/migration). Default-true means a
    freshly founded company gets sandboxed checks for free, consistent
    with "the product works out of the box"; a CEO who wants to opt out
    (e.g. to save sandbox minutes, or because Docker isn't installed and
    they don't want the `could_not_run` noise) flips it off explicitly via
    the Phase 3 Settings toggle.
97. **Detection (`detect_checks`) is pure and synchronous, walking the
    full set of files on the landed branch (`list_tree` + `read_file` per
    path) rather than a git diff of changed files.** A check like
    `pytest` needs to know the whole test file exists and is runnable in
    the checked-out tree, not just that this particular commit touched a
    `.py` file — running against the diff would miss the common case
    where the Engineer edits `add.py` but the pre-existing `test_add.py`
    (unchanged this commit) is what actually needs to pass.
98. **`_glob_to_regex`'s `**` handling special-cases a trailing `/` (`**/`
    translates to `(?:.*/)?`, an optional group) instead of naively
    expanding `**` to `.*` and leaving the following `/` as a literal
    required character.** The naive version made `**/*.py` require at
    least one path segment before the filename, so a root-level
    `test_add.py` (no directory) would never match its own check — caught
    by `test_detect_checks_matches_pytest_and_python_syntax_for_root_test_file`
    failing after the first implementation. Fixed by treating the `**/`
    token as a unit matching zero-or-more leading segments, which is what
    every real glob implementation (`fnmatch`, shell globstar) does.
99. **No new abstract method was added to `WorkspaceManager` to hand
    `_run_checks` a bulk `{path: content}` map.** It's built inline via
    the existing `list_tree` + per-path `read_file` calls, since
    `_run_checks` is presently the map's only caller — adding a new ABC
    method for one call site would be premature abstraction ahead of a
    second, unproven need.
100. **`_run_checks` returns a short plain-language summary (pass/total
    count + each failed check's output truncated to 500 chars), appended
    to `reviewer_context` after the diff text, rather than the raw
    per-check `CheckResult` payloads.** The Reviewer's prompt already
    carries the Change Summary + truncated diff; dumping full sandbox
    stdout/stderr on top would make the prompt harder to reason about for
    little benefit — the Reviewer needs to know *what* failed and roughly
    why, not debug it byte-for-byte. Full per-check results (name,
    status, duration, untruncated output) are still persisted verbatim to
    `TaskORM.check_results` for the CEO-facing UI (Phase 3).
101. **No checks matched or execution disabled both short-circuit
    `_run_checks` to `("", None)` with zero events published** — not even
    a "skipped" `execution.completed`. A document mission or a
    checks-disabled company should look, in the Timeline, exactly like
    execution never existed as a concept for that mission; an
    always-fires-but-sometimes-empty event would force every consumer
    (Timeline rows, Payroll, tests) to special-case a no-op event instead
    of just checking whether the pair of events exists at all.
102. **The CEO-facing checks verdict ("All N checks passed" / "N of M
    checks failed" / "Checks could not run") is computed client-side from
    `TaskORM.check_results` (`lib/utils.ts`'s `checksSummary`), not
    persisted as its own string.** Mirrors decision #93's
    `parseUnifiedDiff` precedent: the raw per-check array is already the
    full source of truth and is small, so deriving the one-line summary
    in three places (`ChangeSummaryCard`, `DecisionCard`,
    `ExecutionResults`) from one shared function costs nothing and avoids
    a second backend-computed string that could drift from the array it
    summarizes.
103. **The Timeline's execution rows need no special-casing in CEO view.**
    `execution.completed`'s `reason` (`"{passed}/{total} checks passed"`,
    set server-side in `_run_checks`) already reads as the plain verdict
    UX_SPEC asks for, so the existing generic `SystemRow` (which renders
    `event.reason`) is the CEO-view row for free. Only Technical view gets
    a dedicated `ExecutionRow` component (`TimelineFeed.tsx`) that expands
    to the per-check chip breakdown — CEO view is intentionally left on
    the default path rather than given its own bespoke row, since the
    default already satisfies the requirement.
104. **The execution-enabled toggle in Company Settings stays interactive
    even when `execution_available` is false (no Docker).** The setting
    is a durable company preference ("should checks run when a sandbox
    becomes available"), not a live control over something happening
    right now — disabling it because Docker is absent today would forget
    the CEO's preference the moment Docker Desktop starts, which is
    exactly the "flip it off once, stays off" ergonomics item 96 already
    established for the opposite direction.
105. **`scripts/seed.py` was broken before this sprint** (missing the
    Sprint 5 `workspace_manager` constructor arg entirely, on top of this
    sprint's new `sandbox_runner` one) — caught only because Phase 3's
    manual verification actually ran `make seed` for the first time in a
    while. Fixed by wiring `LocalGitWorkspaceManager` +
    `DockerSandbox` the same way `main.py`'s `lifespan()` does, rather
    than inventing a seed-only construction path. No `CLAUDE.md`
    "Working Style" self-verify step had caught this because "boot the
    slice when behavior changed" was being read as scoped to whichever
    module changed, not exercised end-to-end via the actual demo path —
    worth remembering `make seed` as part of that check going forward.
106. **Phase 3 UI verification was done without a browser tool**: `tsc
    --noEmit` and `next build` both clean, plus curl-driven smoke tests
    against the live dev servers (page routes return 200, a real code
    mission run through the mock provider end-to-end produces the
    expected `check_results: null` / zero `execution.*` events since the
    mock deliverable never matches a check's `detect_globs`). No actual
    rendered-pixel verification of the new chips/toggle/timeline rows was
    possible in this environment — noted here per CLAUDE.md's instruction
    to say so explicitly rather than claim a browser check that didn't
    happen.
107. **Phase 4 item 4.6 (real-Docker E2E) is pending, not done — Docker
    Desktop is confirmed not running in this dev environment** (a live
    `GET /api/system/capabilities` returned
    `{"execution": false, "reason": "Docker Desktop is not running"}`
    during Phase 3 verification). Per the sprint brief's own fallback
    instruction ("otherwise FakeSandbox E2E + note in DECISIONS.md that
    real-Docker verification is pending"), the closest available
    substitute was exercised instead: the `FakeSandbox`-driven pipeline
    tests (`test_run_checks_detects_and_runs_matched_checks` and
    siblings in `test_execution_pipeline.py`, calling `_land_code_changes`
    / `_run_checks` directly so real `CheckOutcome` data is produced) plus
    a live mock-mode smoke test through the actual running dev server
    (Phase 3, entry #106). Neither exercises the real `docker create` /
    tar-copy / `docker rm` path in `DockerSandbox` itself — that remains
    unverified on this machine. Whoever next has Docker Desktop available
    should run `make sandbox-image` then the 4 skipped
    `@pytest.mark.skipif` tests in `test_sandbox.py` (and ideally one real
    code mission through a running `make dev`) to close this out; nothing
    in Sprint 6's design assumes that verification already happened.

## Sprint 7 — "V1 Hardening & Dockerized Postgres"

108. **Postgres becomes the documented default `database_url`, not an
    additive option** — `docker-compose.yml` (postgres:16, named volume,
    healthcheck) at the repo root, `settings.database_url` defaulting to
    `postgresql+asyncpg://commander:commander@localhost:5432/commander`.
    SQLite (`sqlite+aiosqlite`) stays wired as the zero-dependency
    fallback used only by the test harness (`conftest.py`'s isolated
    temp-file engine, which never reads `settings.database_url`) and any
    quick local script that wants to skip Docker entirely. One seam
    (`Settings.database_url`) drives both `db.py`'s engine and Alembic's
    `env.py` — no second hardcoded connection string anywhere.
109. **Alembic uses the async template (`alembic init -t async`), and its
    generated `env.py` is deliberately never awaited directly.** Alembic's
    async `run_migrations_online()` drives its own internal
    `asyncio.run(...)`, which raises if called from a thread that already
    has a running loop (the FastAPI lifespan, `seed.py`). `db.py` exposes
    a synchronous `upgrade_to_head()` wrapping `alembic.command.upgrade`,
    and every caller on an existing event loop reaches it through
    `asyncio.to_thread(upgrade_to_head)` instead of importing/awaiting
    `env.py`'s coroutine. SQLite still skips Alembic entirely
    (`Base.metadata.create_all`) — it's never a persistent target that
    needs migration history, only ever recreated from scratch.
110. **`make seed`'s Postgres reset is drop-all-tables + re-migrate, not
    `TRUNCATE`.** Keeps the seed script exercising the exact same
    migration path a real deploy would take (`upgrade_to_head()` from an
    empty schema), rather than a second, seed-only schema route that
    could silently drift from the baseline migration. `scripts/seed.py`
    now branches the same way `db.py.init_db()` does: SQLite deletes the
    db file and `create_all`s; Postgres drops every table (+ Alembic's
    own `alembic_version` bookkeeping table) and calls the same
    `upgrade_to_head()` used at boot.
111. **`Settings.model_config`'s `env_file` is anchored to an absolute
    repo-root path (`Path(__file__).resolve().parents[4] / ".env"`),
    not the bare `".env"` pydantic-settings default.** The bare relative
    path is resolved against the process's current working directory,
    which differs between `make dev` (uvicorn launched with cwd=
    `apps/api`, per the working assumption `scripts/seed.py` already
    documented for its own SQLite path) and docker-compose's own `.env`
    auto-discovery (cwd=repo root, where `docker-compose.yml` lives). A
    single `.env` at the repo root is now the one file both the FastAPI
    app and `docker compose` read, regardless of which directory a
    command is launched from — this was caught by a real boot failure
    (Postgres credentials silently falling back to code defaults) during
    Phase 1 verification, not by inspection.
112. **`AnthropicProvider._legible_error` only special-cases 401/403.**
    Every other HTTP error (429/5xx, which `RoutedProviderGateway`
    retries; other 4xx) is left as the original `httpx.HTTPStatusError`
    so `_is_retryable` and server-side logging keep seeing the real
    exception shape. Only auth failures get rewritten into a
    plain-language `RuntimeError` ("Anthropic rejected the configured
    API key... Check the key in Company Settings") — they're never
    transient, so a CEO acting on the message (going to Company Settings)
    is always the right next step, unlike a 5xx where the existing retry
    already handles it silently. Verified against the real Anthropic API
    end-to-end with a deliberately invalid key (`scripts/verify_real_llm.py`
    run with `ANTHROPIC_API_KEY=sk-ant-invalid-test-key-000`): the PM's
    first call failed with a real HTTP 401, `_legible_error` converted it,
    `workflow_engine._run_pipeline`'s existing catch-all turned it into a
    `TASK_FAILED` event carrying only the plain-language string (full
    traceback stayed server-side via `logger.exception`), and the mission
    ended in the `failed` state exactly as designed — no stack trace ever
    reached the CEO-facing surface.
113. **`parse_verdict` was reading the FIRST `**Verdict:**` match
    (`re.search`), not the last, contradicting its own docstring's claim
    of reading "the trailing" line.** Harmless against mock output (which
    only ever emits one such line) but a real risk against real Reviewer
    output, which can ramble and mention "verdict" conversationally
    before its actual sign-off (or, worse, second-guess itself with two
    genuine `**Verdict:**` lines). Fixed to `re.findall(...)` +
    `matches[-1]`, matching the pre-existing docstring's intent exactly.
    Locked in with two new tests in `test_decision_parsing.py`: one
    rambly-but-single-verdict case, and one where an earlier and later
    `**Verdict:**` line actively disagree (`Approved` then, after "on
    reflection", `Changes requested`) — the trailing line must win.
114. **No real Anthropic E2E *mission that reaches a genuine model reply*
    was possible in this environment — no `ANTHROPIC_API_KEY` is
    available here.** This is the one explicit Sprint 7 carryover,
    mirroring Sprint 6 decision #107's precedent: whoever next has a key
    should run `make verify-llm` (`scripts/verify_real_llm.py`, written
    this sprint) once, which drives a full PM -> Engineer -> Reviewer
    mission through the real Anthropic provider in a throwaway SQLite DB
    and workspace dir, prints the parsed verdict + sections + real USD
    cost, and exits non-zero on any failure. What *was* verified for real
    against the live Anthropic API in this environment: the 401
    error-legibility path end-to-end (entry #112) — confirming the
    request genuinely leaves the process, hits `api.anthropic.com`, and
    a real rejection response is turned into the CEO-legible message
    rather than a synthetic/mocked one. The retryable-5xx path (item
    3.4) and the actual "verdict parses from rambly real prose" path
    (item 3.2) remain covered by the unit/integration tests above
    (entries #112, #113) plus the pre-existing `test_provider_retry.py`
    suite, not by a live 429/5xx from Anthropic itself, since that
    can't be triggered on demand without a working key.
115. **`scripts/verify_real_llm.py` runs against a throwaway temp-file
    SQLite database and temp workspace directory, never the project's
    own dev database.** Mirrors `seed.py`'s existing service-layer
    approach (real `projects_service`/`tasks_service`/`workflow_engine`
    calls, not raw SQL) but is safe to run repeatedly and in CI-like
    contexts without disturbing `make seed`'s demo company or requiring
    Postgres/Docker to be up — the point of this script is isolating the
    provider path, not re-verifying the datastore (Phase 1/2 already
    did that) or the sandbox (Sprint 6 already did that).
116. **`/api/health` (liveness) and `/api/health/db` (readiness) are two
    separate endpoints, not one.** Liveness must stay a zero-dependency
    "the process is up" check so it can never itself be the thing that's
    down; DB reachability is a distinct, slower question that deploy
    tooling / the dashboard's API-down banner needs to ask separately.
    Verified live: with Postgres stopped (`docker compose stop
    postgres`), `/api/health` kept returning 200 while `/api/health/db`
    returned 503 with `{"status": "error", "detail": "database
    unreachable: ..."}`; restarting Postgres flipped it back to 200
    within one poll, with no server restart needed.
117. **Boot config validation (`core/boot_checks.py`) runs once at the
    top of `main.py`'s lifespan, before `init_db()`, and turns a bad
    config into `print(..., file=sys.stderr); raise SystemExit(1)`
    rather than an uncaught pydantic/DB exception.** Two checks only:
    `COMMANDER_PROVIDER=anthropic` with no `ANTHROPIC_API_KEY` (would
    otherwise fail confusingly on the first mission's first provider
    call instead of at boot), and a `DATABASE_URL` that isn't
    sqlite/postgresql. `init_db()` failures (e.g. Postgres unreachable)
    are caught the same way, with the DSN redacted
    (`redact_database_url`) before it ever reaches a log line. Verified
    live: booting with `COMMANDER_PROVIDER=anthropic` and an empty
    `ANTHROPIC_API_KEY` printed the plain-language message and exited
    1, without ever reaching `init_db()`.
118. **Frontend resilience is two independent signals, not one.** (a) An
    app-wide `ApiStatusBanner` polls `GET /api/health` every 5s
    (`useApiHealth`, `retry: false` so one failed poll shows the banner
    within 5s rather than waiting out React Query's default retry
    backoff) and renders a sticky top banner only while `isError` — this
    catches the whole API being unreachable, independent of which page
    or query happened to be active. (b) `useEventStream` now surfaces a
    `ConnectionStatus` ("connecting" | "open" | "reconnecting") threaded
    through `RealtimeProvider` -> `useRealtimeConnectionStatus`, and
    `Sidebar` shows a small "Reconnecting…" pill when the SSE connection
    drops. No bounded-retry logic was added on top of the browser's
    native `EventSource`, which already retries indefinitely on its own
    after any drop (confirmed by reading its spec'd behavior — Commander
    never calls `.close()` outside the effect's own cleanup) — the gap
    being closed here is visibility, not retry behavior, since an
    indefinitely-retrying-but-silent connection already met the "never
    lose events forever" bar but not the "CEO can tell something's
    wrong" one. Verified via `tsc --noEmit` + `next build` (both clean)
    and curl-level smoke tests (dashboard shell still returns 200 with
    the API process killed, confirming client-side data fetching is
    what fails, not SSR) — no rendered-pixel/browser verification was
    possible in this environment, per the same caveat as entry #106.
119. **Data-safety audit (item 4.4) found nothing to fix.** Every
    mutating route across `apps/api/app/modules/*/routes.py` was
    enumerated: zero `router.delete(...)` routes exist anywhere: the
    only company-level removal is `POST /api/projects/{id}/archive`
    (`projects/service.archive_project`), which sets `archived = True`
    and is fully reversible, never a hard delete. No mission-delete
    route exists at all. The only real schema/row deletions in the
    codebase (`Base.metadata.drop_all` in `scripts/seed.py`, and
    `op.drop_table(...)` in the baseline migration's `downgrade()`) are
    both CLI-only — neither is imported by `main.py` or reachable from
    any mounted router. No raw `DELETE FROM`/`TRUNCATE`/`session.delete`
    exists anywhere in `apps/api/app`. Dashboard-side, `archiveCompany`
    is the only delete-adjacent action exposed in the UI, and it calls
    the same soft-archive endpoint.

120. **README got a full rewrite, not an incremental edit.** The
    existing `README.md` was pure Sprint-3-era marketing copy (a
    "status-Sprint_3" badge, an "Imagine this" narrative, an OS-analogy
    ASCII diagram) with zero real quickstart, command reference, or
    walkthrough — nothing in it described the actual V1 surface built
    across Sprints 3-7. Patching it in place would have left marketing
    tone bolted onto technical content. Replaced wholesale with: what
    it does, a real quickstart (`make install && make seed && make
    dev`, prerequisites incl. Docker Desktop), a first-company
    walkthrough, mock-vs-real-provider instructions, the full command
    table, health-check endpoints, and an architecture/repo-layout
    summary pointing at `docs/ARCHITECTURE.md` as the source of truth
    rather than duplicating it. Kept internal terminology (Task,
    Project, etc.) in the "Repo layout" and "Architecture" sections
    since those describe code, per CLAUDE.md's own carve-out that only
    UI-facing text is required to use Commander terms; the "What it
    does" and walkthrough sections use Commander terms throughout since
    they describe the CEO-facing product.

121. **`docs/ARCHITECTURE.md`'s "Accepted MVP Tradeoffs" list dropped
    "`create_all` on startup, no migrations"** — false as of this
    sprint's Alembic work (`create_all` now only fires for the SQLite
    test path; Postgres boots run `alembic upgrade head`). Rather than
    just deleting the line, added two tradeoffs that are now the real
    ones at Postgres's scale of use: no connection-pool tuning/read
    replicas/backup tooling (a single local `docker-compose` Postgres
    container is assumed), and `/api/health/db`'s synchronous
    round-trip check having no background-polled cache — both true
    monetary/complexity tradeoffs the CEO-facing docs shouldn't paper
    over.

122. **Sprint 7 complete.** All 6 phases (34/34 items) done: dockerized
    Postgres as the default datastore, Alembic-owned schema, real-LLM
    verification against the live Anthropic API, operational hardening
    (health endpoints, boot validation, frontend resilience), and this
    docs pass (README rewrite, CLAUDE.md status/layout/V1-V1.5-boundary
    update, ARCHITECTURE.md datastore/health/tradeoffs update). No
    V1.5 feature work was started, per the brief's explicit hardening
    boundary. Final verification (`pytest`, `tsc`, `next build`, a
    real-DB boot check) and the closing `chore(sprint7)` commit+push
    follow immediately after this entry.

## Sprint 8 — "V1 Release"

123. **Phase 0 fresh-machine audit was code-based, not a literal fresh
    clone/browser click-through.** No browser tool is available in
    this environment (confirmed absent in Sprint 7 too, DECISIONS
    #106/#118), and this environment already has a populated venv/
    node_modules/Postgres volume, so a truly isolated fresh-clone
    simulation wasn't possible. Substituted: (a) re-verified every
    README-documented command still runs correctly against the current
    repo state (same substance as a dry run — catches broken
    instructions, just not first-install friction like slow `pip`/
    `pnpm install`), and (b) an Explore-agent audit read all 10 routes'
    actual source (page components + their TanStack Query hook usage)
    to determine, per route, whether empty/loading/error states are
    handled, and grepped for internal-terminology leaks in rendered
    JSX text. Findings:
    - **No route anywhere handles TanStack Query's `isError`** — a
      failed fetch either shows the loading state forever or renders
      with `undefined` data. This is the single biggest real gap and
      drives Phase 1 item 1.3.
    - Three detail pages (Mission detail, Employee profile, Report
      detail) conflate "loading" with "not found": if the id doesn't
      resolve, they show "Loading…" indefinitely instead of a
      not-found message.
    - Employees grid (`/company/[id]/employees`) has no empty state at
      all — an empty roster silently renders a blank grid.
    - Missions kanban empty columns show a generic "Nothing here." for
      every column regardless of which column it is.
    - The audited "Reviewer audit" phrase in Company Settings
      (`settings/page.tsx:162`) is NOT a terminology leak — "Reviewer"
      is the Employee's actual role title (`templates/software_company.py`
      role `title="Reviewer"`), already used elsewhere in the UI for
      that Employee's card/profile. Flagged by the audit as a
      precaution but confirmed a false positive on inspection; left
      as-is except for a small grammar tighten ("before the Reviewer's
      audit").
    These are folded into PROGRESS.txt Phase 1 as concrete items
    rather than re-listed here.

124. **Phase 1 experience-coherence implementation.** Added a shared
    `ErrorState` component (`components/ErrorState.tsx`, modeled on
    the existing `EmptyState`) and wired `isError` from every
    `useQuery`/`useInfiniteQuery` call site into it across all 11
    routes (My Companies, Headquarters, Missions kanban, Mission
    detail, Employees grid, Employee profile, Decisions pending+
    history, Timeline, Reports list, Report detail, Company Settings,
    Workspace). Headquarters aggregates five independent queries with
    no single fetch to key off, so it ORs their `isError` flags and
    renders one page-level `ErrorState` rather than five partial ones
    — simpler and matches how the page already reads as one unified
    view. Workspace's three panels (file tree, file viewer, merge
    history) use small inline `text-status-red` messages instead of
    the full padded `ErrorState` card, since each panel is small and a
    fetch failure in one (e.g. merge history) shouldn't visually
    dominate a still-working file tree next to it — precedent: the
    panel already used inline text for its own empty states.
    Fixed the three loading/not-found conflations (`MissionDetail`,
    `EmployeeProfile`, `ReportDetail`) by splitting the guard into an
    `isLoading` branch and a separate `isError || !data` branch, the
    latter distinguishing "couldn't fetch" from "doesn't exist" in the
    description text. Added the missing Employees-grid `EmptyState`
    and replaced the kanban's one shared "Nothing here." with a
    per-column `emptyText` (backlog/developing/needs-decision/done),
    each grounded in what that column's StatusWord actually means.
    Terminology sweep (item 1.4): grepped rendered JSX text across
    `app/` and `components/` for the internal→UI term pairs in
    CLAUDE.md; zero leaks beyond the already-confirmed-false-positive
    "Reviewer" role title. Copy-voice pass (item 1.5): per UX_SPEC §8
    item 6 (company-voice vs. interface-voice), had an Explore-agent
    audit flag candidate mismatches. Most flagged items ("Say hello to
    the Department.", "Found your first AI company above…") were
    judged consistent on review — they're all instances of the same
    intentional "invitation to act" empty-state pattern the sprint
    brief itself asks for (item 1.1), not voice mixing. Genuine fix:
    tightened kanban empty-column copy to a consistent "Nothing/
    Nobody…" opener across all four columns (was "No Missions queued."
    breaking the pattern the other three already used). Left
    `SituationReport`'s "Reading the room…" loading line as-is — it's
    atmospheric flavor for the PM's report loading, not literal
    first-person impersonation, and doesn't fabricate any claim.

125. **Phase 2 demo honesty & simulation labeling.** Added a calm
    amber "Simulation mode" pill (title tooltip explaining what it
    means) that renders only when `company.provider === "mock"`, in
    both `Sidebar` (persistent across every company page) and
    `CompanyCard` (My Companies list) — replacing the old raw-value
    chip that printed the internal string `mock`/`anthropic` directly
    (`Sidebar.tsx`, `CompanyCard.tsx`). Hidden entirely in real mode
    per the brief, rather than showing a "Live"/"Real" counterpart —
    the brief only asked for the mock signal, and a second permanent
    badge for the normal case would be visual noise.
    Strengthened the mock deliverable's honesty signal in
    `mock_provider.py`: the revision-branch Change Summary (re-runs
    after CEO feedback) previously read as genuine follow-up work with
    no simulated-content signal at all; added one; the mock Reviewer's
    audit text (`_audit_text`) previously read as a real completed
    review — added a fixed "_Simulated review (mock provider)..._"
    line before the trailing `**Verdict:**` (verified `parse_verdict`
    still finds it correctly — it takes the *last* `**Verdict:**`
    match, so text before it is safe; confirmed via
    `test_mock_provider.py`, still 5/5 passing).
    Company Settings AI Provider control: relabeled the select options
    and rewrote the helper copy to state the actual mock/real
    consequences (no real API calls in Simulation mode vs. real
    Anthropic billing that appears in Payroll).
    **Found and deliberately left alone a real fabrication case**:
    `MockProvider._fabricate_usage` invents token counts from word
    counts, and `model_registry.PRICE_PER_MILLION_TOKENS` has non-zero
    prices for all three `mock-*-v1` refs (`cost_for("mock-builder-v1",
    1_000_000, 1_000_000) == $18.00`, asserted by
    `test_costs.py::test_cost_for_computes_from_the_price_table`) — so
    Payroll shows non-zero, plausible-looking dollar figures in mock
    mode with no real API call behind them. This is pre-existing,
    intentional Sprint 4 ("Real Intelligence") behavior, not a Sprint 8
    regression: mock needs *some* numbers for the Payroll page to be
    demoable at all, and zeroing mock pricing would be a tested
    feature-behavior change, not polish — out of scope for a
    coherence/honesty sprint whose own brief says "no new capability."
    Resolved the honesty concern the way the brief's own design
    decision intends (labeling, not removal): the CEO can no longer be
    on any company page without the persistent "Simulation mode"
    sidebar badge in view, and Company Settings now explicitly states
    mock Payroll figures are "simulated numbers for demo purposes, not
    real spend." Did not add a per-figure "(simulated)" suffix next to
    every dollar amount on every page (Headquarters stat card,
    EmployeeCard) — judged as visual clutter beyond what the
    always-visible sidebar badge already covers, consistent with the
    brief's "no visual redesign" constraint. Flagging here in case a
    future sprint wants stricter per-figure labeling.

126. **Phase 3 packaging & one-command run.** `docs/prompts/
    sprint-4.5-employee-profiles.md` (item 3.6): the working tree had
    an *uncommitted* local change re-appending the entire 307-line
    `docs/design/UX_SPEC.md` content verbatim onto the end of this
    already-committed sprint brief, byte-identical (empty `diff`) to
    the real `UX_SPEC.md` file — an accidental duplication, not
    intentional content. Reverted the file to its clean, committed
    HEAD (172 lines; `git checkout --`) rather than editing, since the
    committed version was already correct and nothing unique lived in
    the duplicated tail. `.claude/scheduled_tasks.lock` (item 3.5):
    confirmed via `git log` it carries no meaningful history (one
    prior commit, "script 4 completed") and is local scheduler runtime
    state, not product state — added to `.gitignore` and `git rm
    --cached`'d rather than left tracked-but-ignored, since a tracked
    file that changes every session was exactly the noise Phase 0's
    audit (#123) flagged.
    `make help` (item 3.2): added a `## comment`-driven `help` target
    (grep + awk over `Makefile`, a standard idiom) as `.DEFAULT_GOAL`,
    with a one-line `##` description on every existing target;
    verified the parsing pipeline directly since no `make` binary is
    present in this dev environment (Windows, no make in PATH — same
    constraint noted in Sprint 7). Added `make demo` (`seed` + `dev`)
    per the brief's "your call" invitation: the documented happy path
    was already just two commands, but collapsing to exactly one
    matches the brief's own bar ("reduces the happy path to one
    obvious command") and costs nothing (thin wrapper, no new logic).
    README (items 3.1, 3.4): prerequisites line now explicitly splits
    Docker's two uses — required for Postgres, optional for the
    execution sandbox — since the old single "Docker Desktop (running)"
    line read as one unconditional requirement and buried the sandbox's
    documented degrade-gracefully behavior. Added one explicit sentence
    to the "What it does" Mission bullet stating what happens with no
    Docker/no sandbox image/toggle off (skips straight to review, no
    errors, no degraded UI) rather than leaving it only inferable from
    the Architecture/Settings sections. Verified every command named in
    the README (`make install/db-up/db-down/db-upgrade/db-downgrade/
    seed/dev/demo/test/sandbox-image/verify-llm`) resolves to a real,
    present script or `package.json` entry — same "verify against
    current repo state, not a literal fresh clone" substitute
    methodology as Phase 0 (#123), since no browser/fresh-VM tool is
    available here either. `.env.example` (item 3.3): re-diffed against
    `core/config.py`'s `Settings` fields — already complete (every env
    var documented with a comment, real-key path already noted as
    "can also be set at runtime from Company Settings"); no changes
    needed.

127. **Phase 4 release verification.** 4.1: full green —
    `apps/api` pytest 157 passed / 4 skipped (269s), dashboard
    `pnpm typecheck` clean, `pnpm build` clean (all 13 routes compile,
    static pages generate). 4.2 (E2E run #1, mock, fresh PG volume):
    `docker compose down -v` to genuinely destroy the existing
    container+volume (local demo data only, fully reseedable — not the
    kind of destructive op that needs asking, and the brief itself
    specifies "fresh PG volume"), `docker compose up -d postgres` +
    `alembic upgrade head` (single `9fd1f513c939` baseline migration,
    confirms Sprint 7's schema consolidation is still the true head) +
    `scripts/seed.py` all ran clean against the empty volume. Drove
    one full Mission through the real running API (not just tests):
    create code Mission -> assign -> PM plan -> Engineer commit
    (`mission/981b542f`, real branch + commit sha) -> Reviewer verdict
    (Approved, mock honesty line present per #125) -> CEO Decision
    with full Problem/Recommendation/Risk/Impact anatomy -> approve ->
    `branch.merged` -> Mission `completed`. Cross-checked Payroll
    (`GET /projects/{id}/costs`, non-zero per-agent USD as expected per
    #125), Situation Report (correctly dropped to "1 decision waiting"
    after approving one of the two seeded-pending decisions), and the
    event feed (`task.completed` -> `approval.granted` ->
    `branch.merged` -> `approval.requested` -> `workflow.review_completed`,
    in the right causal order) — all coherent. Re-ran `scripts/seed.py`
    afterward to clear the verification Mission back to the clean demo
    state, same precedent as Sprint 4.5 Phase 0.1. 4.3 (E2E run #2,
    real Anthropic): no `ANTHROPIC_API_KEY` is configured in this dev
    environment (`.env` has the key line empty, no env var set) — real
    Anthropic behavior was already verified live in Sprint 7 (see
    CLAUDE.md's Sprint 7 status paragraph: `_legible_error()`,
    `parse_verdict` trailing-line fix, both verified against the real
    API then). `make verify-llm` (`scripts/verify_real_llm.py`) remains
    the documented one-command way to re-verify with a key; flagging
    the absence of a fresh real-key run as this sprint's one carryover
    limitation rather than skipping it silently.

## Sprint 8.5 — V1.1 Kickoff (Documentation Integration)

128. **V1.5 plan superseded by V1.1, not merged with it.** The old
    two-phase roadmap (V1 in Sprints 7-8, then a monolithic "V1.5" of
    Agent Harness + CTO + PM Specification + Project Memory in one
    block, spec'd in a `docs/V1.5-SPEC-refined.md` that was never
    actually created) is retired outright. V1.1 replaces it with a
    12-sprint phased roadmap (CLAUDE.md §9, Sprints 9-20) that breaks
    the same underlying capability set into ordered, independently
    shippable phases (reliability -> org model -> planning -> CEO
    experience -> harness -> memory -> cleanup), each gated by its own
    sprint brief. Reason: a single undifferentiated "V1.5" sprint was
    too large to brief, build, or verify as one unit — this sprint's
    own three-document rewrite is the first artifact of that
    decomposition. `docs/V1.5-SPEC-refined.md` never existed on disk
    (grep confirmed); no reference to it survives outside historical
    `docs/prompts/` sprint briefs and one already-past-tense
    `docs/DECISIONS.md` entry (#122, Sprint 7), both preserved as
    record per the brief's own instruction not to rewrite history.

129. **Two-axis org model (decision vs. delegation) instead of one
    chart.** A single org tree can't represent both facts at once:
    PM and CTO are peers while a Specification is being planned
    (neither reports to the other), but once work is approved, the
    CTO assigns down to Employees and results climb back through the
    PM (CLAUDE.md §2, ARCHITECTURE.md §1.1). Collapsing this into one
    hierarchy diagram would force a false reporting relationship in
    one phase or the other. Drawing the two phases as two separate,
    explicitly-labeled diagrams (Decision axis / Delegation axis) is
    the documents' own resolution, carried into both CLAUDE.md and
    ARCHITECTURE.md identically (verified word-for-word in Phase 3.3).

130. **Role/Employee separation, with leadership roles as
    data-layer-enforced singletons.** V1 conflates "the PM" with a
    hardcoded Agent record; V1.1 splits this into an immutable Role
    (owned by the Template: prompt contract, tool grants, workflow
    position) and an unlimited-count Employee (owned by the CEO:
    name, model, profile) bound to a role_key. Leadership roles (PM,
    CTO, Reviewer) stay singletons — never zero, never two, enforced
    at the data layer rather than by convention — because the CEO's
    one conversational counterpart (Rule #11) and the Reviewer's
    trailing-Verdict contract (prompt_builder) both depend on there
    being exactly one of each. Worker roles (Backend/Frontend
    Engineer and beyond) are deliberately unbounded so hiring a
    second Engineer on a different model is a staffing action, not a
    schema change.

131. **Invariants #11-17 (CLAUDE.md §4), one line each on why:**
    - **#11** (CEO talks only to the PM) — keeps the org metaphor
      literal; a CEO who can also DM the Reviewer isn't running a
      company, they're prompting workers, which is the exact
      distinction Commander is selling.
    - **#12** (tools are template-granted to a Role, only
      `run_checks` exists) — extends Rule #9 into the harness era so
      the same "whitelist, never a blocklist" guarantee holds once
      agents get tool loops in Sprint 16, before that code exists to
      audit.
    - **#13** (every autonomous loop runs under a budget) — without
      this, Sprint 16's tool loops and Sprint 12's PM<->CTO discussion
      have no bound; budget exhaustion must be a first-class
      organizational event (`blocked` + reason), not a silent hang or
      infinite retry.
    - **#14** (Project Memory is a projection over events, no second
      store) — keeps the single-event-stream guarantee (Rule #8) from
      quietly growing a second source of truth once Memory ships.
    - **#15** (cross-account access is 404, not 403) — the smallest
      correct rule once multi-account auth exists (Sprint 9); 403
      confirms a resource exists for an account that shouldn't know
      that.
    - **#16** (roles are data, never a hardcoded role-name branch) —
      the concrete engineering promise that adding Designer/QA/DevOps
      later is a template-data change, not an engine change; directly
      enforces the Role/Employee split (#130) in code.
    - **#17** (new CEO-facing capability is a Widget or Sidebar page)
      — keeps the PM conversation area from accreting ad-hoc panels
      as the product grows past V1.1; the conversation's stability is
      UX_SPEC's central bet (§1, §10.4).

132. **Three documents, not four.** CLAUDE.md (implementation rules),
    ARCHITECTURE.md (system structure), UX_SPEC.md (CEO experience)
    already covered day-to-day rules, structure, and experience
    respectively with no real gap; a fourth document would either
    duplicate one of the three or fragment a concern (e.g. "product
    terminology") that reads better living inside CLAUDE.md next to
    the rules that enforce it. ARCHITECTURE.md §10 codifies the
    precedence order for when the three ever conflict (ARCHITECTURE >
    UX_SPEC > CLAUDE.md, narrowest scope wins) — this was itself
    checked for consistency across all three docs in Phase 3 and
    found to be stated identically only in ARCHITECTURE.md itself
    (the other two don't restate it, which is fine — it's a
    tie-breaking rule for the docs' own maintainers, not CEO- or
    implementation-facing content).

133. **`situation` module repurposed, not deleted, this sprint.** The
    standalone Situation Report UI block is removed in the V1.1
    target (UX_SPEC §3.2 — its content is absorbed into the PM's
    opening conversational report so the CEO doesn't read the same
    status twice from two different voices), but the module and its
    `GET /projects/{id}/situation` endpoint stay exactly as they are
    in the codebase through this sprint (ARCHITECTURE.md §6.1: "⚠️
    Repurposed in V1.1"). The actual code change — folding its output
    into the PM conversation — is out of scope until whichever sprint
    builds the PM Conversation surface (Sprint 13 per CLAUDE.md §9);
    this sprint only had to confirm the module isn't prematurely
    deleted or orphaned by the new docs, which it isn't.

134. **Template-driven architecture ships with exactly one template.**
    ARCHITECTURE.md §1.3 defines a Template as a data document (roles,
    workflow, approval_flow, tool_registry, prompt_templates,
    deliverable, vocabulary, starters) specifically so a second
    template is "add a data file," not "redesign a system" — but
    §9.2 (unchanged from the old V1 UX_SPEC's §10 Future Expansion
    Strategy analysis) holds that shipping a second template before
    `software_company` sustains real usage is premature: non-software
    domains lack software's pass/fail verifiability, so a Reviewer's
    verdict degrades into unfounded opinion and the Decision loop —
    the product's core mechanic — becomes theater. Building the
    generality now while deliberately not exercising it with a real
    second template is the documented tradeoff; it was carried
    forward from the old UX_SPEC essentially unchanged, which this
    sprint's Phase 0 read confirmed.

135. **Phase 0-1 judgment calls.** (a) The three new documents were
    already staged as uncommitted working-tree modifications rather
    than needing to be authored or fetched — treated as "provided
    with this brief" per the brief's own framing, not as a discovery
    requiring separate installation steps. (b) Phase 1.4's "no
    duplicate copy" check was read narrowly (no exact/near-verbatim
    duplicate of the *new* docs' content) rather than broadly (no
    stale architecture doc of any kind); `docs/backend/MODULES.md`,
    `docs/backend/DEPENDENCIES.md`, and `docs/adr/README.md` are
    Sprint-2-era docs describing a module/dependency model that
    predates even the old V1 ARCHITECTURE.md and no longer matches
    reality, but they aren't literal duplicates of the new docs, so
    they're reported as a finding rather than treated as a Phase 1.4
    failure or silently deleted (deletion is a repo-cleanup action
    with no sprint-brief authorization here).

136. **Phase 2 judgment calls.** (a) `workspace_manager`'s §6.1 claim
    of "no symlink escape" protection was re-verified directly rather
    than accepted as a gap on a subagent's report of "no explicit
    `is_symlink()` call": `validate_path()` resolves the candidate via
    `Path.resolve()` (which follows symlinks) and then checks
    `relative_to(repo_root)`, and `local_git.py` only ever
    `write_text()`s into that resolved path — so the guarantee holds
    via a different, equally valid mechanism, and the claim is
    CONFIRMED true, not a discrepancy. (b) ARCHITECTURE.md §7.1's
    "Sprint 9 adds `--cap-drop ALL`..." clause was judged
    correctly-future-tense rather than an overstatement, since it
    names the sprint explicitly and matches §6.4(5)'s independent
    statement of the same gap — read literally, it makes no claim
    about the current state. (c) PROGRESS.txt's header item-count was
    corrected from a pre-existing 40 to the true count of 35 (summed
    directly from the file's own `[ ]`/`[x]` lines) when it was
    noticed the header no longer matched item state — a bookkeeping
    correction, not a scope change.

137. **Phase 3 judgment calls.** (a) CLAUDE.md §2's worked example
    (Backend Engineer: Kim/Lee/Park) and UX_SPEC §5.4's worked example
    (same three names, but Park under Frontend Engineer instead of
    Backend Engineer) disagree on which role Park illustratively
    holds. Both are illustrative only — no architecture or scope is
    affected either way — but which one is "correct" is an authorial
    choice, not a typo, so it's reported rather than silently
    resolved in one document's favor. (b) Three ARCHITECTURE.md
    citations of a nonexistent "UX_SPEC §11" (the current UX_SPEC
    only goes to §10) were treated as mechanical errors — wrong
    section numbers, not wrong content — and corrected in place to
    the sections that actually carry the cited claims (§10.2, §3.2,
    §3-§4). (c) ARCHITECTURE.md §8 states V1's "My Companies" and
    "Headquarters" pages are "not discarded in V1.1," but UX_SPEC
    v2.0's own IA tree (§2) and its "Sidebar Pages (V1 surfaces,
    retained)" list (§7) rename "My Companies" to "Projects" and omit
    Headquarters entirely, with CEO Workspace replacing it as the
    default landing. None of the three documents states explicitly
    whether Headquarters survives as a page, is absorbed into
    Widgets, or is dropped — this is a real design gap, reported
    rather than decided, since resolving it means choosing V1.1 IA,
    which is out of this sprint's remit.

138. **Phase 4 judgment calls.** (a) Audited every "V1.5" mention
    repo-wide (`git grep`): the only hits outside historical
    `docs/prompts/` briefs and one already-past-tense DECISIONS.md
    entry are the checklist line in this sprint's own kickoff brief
    and PROGRESS.txt describing this very task — i.e. Phase 4.1 was
    already satisfied by the new documents' own text before any edit
    was made this phase; no removal was needed or performed. (b) This
    session's tool environment has no `make` binary on `PATH` (checked
    via both the Bash and PowerShell tools, and `where`/`choco`
    turned up nothing). "Verify every command actually runs" was
    therefore done structurally instead of by literal execution:
    every Makefile target's underlying script/binary/compose file was
    confirmed present on disk (`apps/api/.venv`, `docker-compose.yml`,
    `sandbox/Dockerfile`, `scripts/seed.py`,
    `scripts/verify_real_llm.py`, Alembic), and `make test`'s core
    step (`pytest`) was already proven passing end-to-end in this
    sprint's own Phase 0 baseline (157 passed / 4 skipped). Running
    `make dev`/`make seed` live was additionally out of scope on its
    own merits — they start long-lived servers and mutate the local
    Postgres volume, neither of which belongs in a documentation-only
    sprint. Flagged as a carryover limitation, not glossed over.

## Sprint 9 — Phase A: Foundation & Authentication

139. **Headquarters absorption made concrete, not just asserted.** Sprint
    8.5 (#137c) flagged that no document actually said what happens to
    Headquarters in V1.1. The Sprint 9 brief §2.12(a) resolved this:
    Headquarters does not become a Sidebar page, it is absorbed into the
    CEO Workspace at the same route. Implemented as: (1) `CLAUDE.md`
    terminology table row changed from `Dashboard | Headquarters` to
    `Dashboard | CEO Workspace`, while §8's "CEO surface:" sentence was
    deliberately left saying "Headquarters" because that sentence
    describes V1 as-built reality, not the V1.1 target — conflating the
    two would misdescribe what's actually shipping today; (2) a new
    paragraph in §9's V1/V1.1 boundary section states the absorption
    explicitly as a roadmap decision, not an open question; (3)
    `docs/ARCHITECTURE.md` §8 gained the four-row block-to-widget mapping
    table (Decision strip → Pending Approvals widget, Situation Report →
    PM Report, Vitals → Progress/Employees/Risks/Costs widgets, Timeline
    excerpt → Timeline widget) plus a one-line rationale (the widget dock
    already replicates Headquarters, so keeping both duplicates surface
    and forces the CEO to guess which screen to check); (4) `UX_SPEC.md`
    §7's intro paragraph now states the absorption inline rather than
    leaving Headquarters's absence from the Sidebar-page list unexplained
    silence. §2's IA tree was left untouched per the brief — it was
    already correct.

140. **Pacing switch implemented as a module-level mutation in
    `conftest.py`, not a fixture.** `Settings` (`core/config.py`) is a
    single process-wide singleton (`settings = Settings()`), so a
    session-scoped autouse fixture would have worked but adds
    indirection for no benefit — setting
    `settings.commander_pacing_enabled = False` once at conftest import
    time (before any test collects) is simpler and has identical effect,
    since nothing re-reads `Settings` fresh per test. Measured effect:
    157 passed / 4 skipped in 109.59s with pacing off vs. the recorded
    349-369s pacing-on baseline from Sprint 8.5's own `make test` runs —
    about a 3.2x reduction, consistent with removing 0.5-1.5s sleeps from
    4 pipeline beats across the full-pipeline-style tests. Production
    default stays `True`; only the test environment flips it.

141. **`--read-only` deliberately not added to the sandbox `docker
    create` call, matching the brief's explicit instruction.** Check
    commands (pytest, `node --test`, etc.) write ordinary artifacts into
    `/workspace` during normal operation (`__pycache__`, coverage files,
    node_modules caches) — `--read-only` would fail every such check
    closed, not just malicious writes. `--cap-drop ALL` and
    `--security-opt no-new-privileges` were added instead, which remove
    privilege-escalation surface without blocking legitimate writes; the
    command itself remains trusted template data per Rule #9, never AI
    output, so write access inside the sandbox isn't an escalation path.
    Reasoning recorded inline in `docker_sandbox.py` per the brief's
    instruction to comment the omission, not just note it here.

142. **`ARCHITECTURE.md` §7.1's "*Sprint 9 adds `--cap-drop ALL`...*"
    sentence was left unchanged in Phase 0** even though the feature it
    describes is now implemented as of this phase. Sprint 8.5 (#136b)
    already judged this sentence correctly-future-tense; updating it to
    present tense mid-sprint would desync it from the rest of §7.1's
    still-forward-looking Sprint 9 authorization-section content (§7.2,
    written as target-state) before the sprint's own Phase 5 As-Built
    sync pass. Left as a tracked item for Phase 5.4 rather than patched
    piecemeal, so the whole section updates once, consistently.

### Phase 1 — Operational reliability

143. **`TaskSnapshot` frozen dataclass replaces the `TaskORM` row inside
    the pipeline coroutine.** `_run_role`/`_land_code_changes`/
    `_run_checks` previously held a `TaskORM` fetched in one session and
    read its attributes across later `await`s on the provider — a
    detached-instance read that only worked by accident (SQLite's lax
    session semantics) and would break louder on Postgres under load.
    `TaskSnapshot.from_orm()` is built once per pipeline run from a row
    read inside its own session block; every later stage reads the
    snapshot, never the row. The one field that legitimately changes
    mid-run (`branch_name`, set once code lands) is threaded forward via
    `dataclasses.replace()` rather than re-fetching the whole row.
144. **`asyncio.CancelledError` is caught inside `_run_role` itself, not
    only at the outer `_run_pipeline` handler.** `CancelledError` is a
    `BaseException` since Python 3.8, so a bare `except Exception` at any
    level silently misses it. `_run_role` needs its own catch because the
    Agent must be released back to `idle` (via `_release_agent_to_idle`,
    which walks the real `AGENT_TRANSITIONS` graph — e.g.
    `WAITING_REVIEW` has no direct edge to `FAILED`, only via
    `COMPLETED`) before the cancellation propagates; the outer handler in
    `_run_pipeline` is only responsible for the Mission's own state
    (→ `cancelled`) and the `TASK_CANCELLED` event. Both handlers
    re-raise `CancelledError` rather than swallowing it, per correct
    cancellation semantics.
145. **The three `_check_budget()` call sites were chosen so a raised
    `BudgetExceededError` always lands on a Mission state from which
    `blocked` is a legal transition** (`TASK_TRANSITIONS` allows
    `blocked` from `in_progress`, `in_review`, and `pending_approval`,
    not from `created`) — checks sit right after the state has already
    moved into `in_progress` (before PM), immediately before the Engineer
    stage (still `in_progress`), and right after the `in_review`
    transition (before Reviewer). This keeps `_block_task_on_budget`'s own
    transition call simple: it never needs to special-case which state
    it's blocking from.
146. **`_check_budget`'s elapsed-time calculation normalizes
    `task.created_at` to UTC-aware before subtracting.** SQLite/aiosqlite
    (the test harness's DB) returns a naive `datetime` for a
    `DateTime(timezone=True)` column; Postgres (production) returns a
    tz-aware one. Subtracting a naive value from
    `datetime.now(timezone.utc)` raised `TypeError` and broke 12
    previously-green tests the moment the budget guard's per-stage checks
    were wired into `_run_pipeline`. Fixed by attaching `timezone.utc` to
    a naive `created_at` before the subtraction, with the discrepancy
    documented inline rather than switching the test DB engine (SQLite
    remains the deliberate fast-test choice per existing convention).
147. **Orphan-mission recovery runs once at API boot, inside `lifespan`
    right after `init_db`, using a synthetic `SYSTEM_ACTOR`** (not a real
    Employee) as the event author. Recovery isn't triggered by a
    schedule or a request — a Mission can only be "orphaned" (stuck
    `in_progress`/`in_review` with no live coroutine) because the
    previous process died mid-pipeline, and the only reliable moment to
    detect that is the next process's own startup, before it starts
    accepting traffic that could race a fresh assignment onto the same
    row.
148. **Mission cancel has two paths in `CommanderWorkflowEngine.cancel_task`,
    not one.** If the task still has a live entry in the new `_running`
    registry (`dict[str, asyncio.Task]`), cancel calls `.cancel()` on the
    coroutine and lets the pipeline's own `CancelledError` handler finish
    the transition to `cancelled` (so the Agent gets released correctly
    per #144). If there's no live coroutine (e.g. `pending_approval`,
    where the pipeline already exited normally and is just waiting on a
    CEO decision), cancel falls back to a direct DB transition via
    `_finish_task`. Collapsing these into one code path would have meant
    either spawning a no-op coroutine just to cancel it, or duplicating
    the transition-and-event logic outside the pipeline — the two-path
    design keeps the pipeline coroutine as the single writer of its own
    Mission's terminal state whenever one is running.

### Phase 2 — Pipeline data-ification

149. **`StageSpec.kind` is a closed `Literal["plan", "produce", "review"]`,
    not an open string, even though the brief's own example table (§4.1
    of `ARCHITECTURE.md`) lists a fourth kind (`discuss`) for Sprint 12.**
    Adding `"discuss"` now, with no engine branch that does anything with
    it, would be dead code the moment it shipped — Rule #16's "roles are
    data" doesn't mean "kinds are unbounded before the behavior exists."
    The `Literal` stays exactly as wide as the engine's actual `if
    stage.kind == ...` dispatch in `_run_pipeline`; Sprint 12 extends
    both together.
150. **`resume_from` changed from a `role_key: str` to a stage `index:
    int`, per the brief's explicit instruction.** The old code resumed
    rework at `_ENGINEER.key` — a role name that only worked because
    "the Engineer" and "the one produce stage" were the same fact. Once a
    `kind` can repeat (a second `produce` role in Sprint 11), "resume at
    role X" is ambiguous the moment two stages share that role. A stage
    index has no such ambiguity. `_REWORK_STAGE_INDEX` is computed once
    at import time via `first_stage_index(TEMPLATE.pipeline, "produce")`
    against the *real* `software_company` template — it is not
    recomputed per-call, since only one template exists in this sprint
    and the value cannot change at runtime.
151. **Verification for "the engine can walk an arbitrary sequence" used
    a 4-stage test-only pipeline built by `dataclasses.replace(TEMPLATE,
    pipeline=...)` and reused the real template's three roles (`pm`,
    `engineer` twice, `reviewer`), rather than inventing fourth and fifth
    role/agent rows.** The brief prohibits adding a CTO or Frontend
    Engineer this sprint (§2.8's closing line) — reusing `engineer` for
    both `produce` stages tests the actually-required property (the same
    `kind`, and the same `role_key`, can appear twice) without smuggling
    in Sprint 11 scope. The test file monkeypatches the module-level
    `TEMPLATE` name inside `app.modules.workflow_engine.engine` (not the
    frozen `app.templates.TEMPLATE` singleton, which cannot be mutated in
    place) so the swap is scoped to each test and invisible to every
    other suite. `tests/test_pipeline_stages.py` also asserts the real
    template's pipeline is still exactly 3 stages, as a guardrail against
    Sprint 10/11 scope leaking in early.
152. **`ARCHITECTURE.md` §7.1's Sprint-9-sandbox-hardening sentence was
    updated in this phase's commit, not deferred to Phase 5 as Decision
    #142 originally planned.** Phase 2's own checklist item (§3 "2.7
    docs/ARCHITECTURE.md의 워크플로우 엔진 서술 동기화") required a pass over
    `ARCHITECTURE.md` regardless, and §6.4's "Known structural debt
    entering V1.1" list — which item 5 is part of — needed the same pass
    to mark all five Sprint-9 debt items resolved. Fixing the one
    remaining stale sentence in the same edit was strictly cheaper than
    reopening the file a third time in Phase 5 for a single word change;
    Decision #142 is superseded by this entry, not contradicted by it.

### Phase 3 — Auth backend

153. **`fa793dce62cb_accounts_and_sessions` migration rewritten to use
    `op.batch_alter_table` for `projects.owner_id`'s `add_column` +
    `create_foreign_key`, instead of two bare top-level `op` calls.**
    Smoke-testing the migration directly (`alembic upgrade head` against
    a throwaway sqlite file — not just `Base.metadata.create_all`, which
    is what `conftest.py` uses and never exercises Alembic at all) failed
    with `NotImplementedError: No support for ALTER of constraints in
    SQLite dialect`. `core/config.py`'s own comment documents sqlite as a
    supported "zero-dependency fallback ... for tests and quick local
    runs," not a test-only shim, so a migration that only works on
    Postgres would silently break that documented path the moment
    someone ran `db-upgrade` against a sqlite `DATABASE_URL`. Batch mode
    is a no-op wrapper on Postgres (plain in-place `ALTER TABLE`) and
    does the copy-and-move recreate strategy on sqlite — verified
    upgrade → downgrade → re-upgrade all succeed against a throwaway
    sqlite file. No other migration in `alembic/versions/` currently adds
    a column + FK together, so this is the first time the gap surfaced.
154. **`core/ownership.py` gained one generic `resource_owned_by(session_
    factory, orm_class, resource_id, owner_id)` instead of a bespoke
    ownership check per resource type (tasks, approvals, agents,
    reports).** All four ORM classes carry a direct `project_id` column
    (confirmed by reading `db_models.py`), so the check is identical
    shape every time: load the row, load its project, compare
    `project.owner_id`. `project_owned_by` (the direct project-id check)
    stays separate since a `ProjectORM` has no `project_id` column to
    read — the two helpers cover the two shapes that actually exist in
    the schema, not a speculative third.
155. **`approvals/service.py`'s `list_pending` gained an `owner_id: str |
    None = None` third parameter rather than reordering `project_id` to
    make room for it.** `list_pending` had ~18 existing positional call
    sites (`list_pending(session_factory, project.id)`) across tests and
    scripts; putting `owner_id` first would have silently rebound every
    one of those calls to the wrong parameter and made `project_id`
    newly-required, breaking them all with a `TypeError` rather than a
    visible signature change. Caught by re-grepping every call site
    before running tests, not by a test failure. This also fixed a real
    cross-account data leak: `list_pending(project_id=None)` previously
    returned pending approvals for *every* account's projects, not just
    the caller's — the route now passes `owner_id=user.id` whenever no
    `project_id` filter narrows the query, and the service JOINs through
    `ProjectORM.owner_id` to scope it (Rule #15).
156. **`auth/service.py`'s `resolve_session` normalizes `row.expires_at`
    to timezone-aware before comparing against `datetime.now(timezone.
    utc)`, using the same `tzinfo is None -> .replace(tzinfo=utc)` pattern
    already established in `workflow_engine/engine.py` (Decision #146) and
    `_check_budget`.** SQLite round-trips `DateTime(timezone=True)` as
    naive; Postgres does not. Discovered via the new `tests/test_auth.py`
    — 7 of 14 tests failed with `TypeError: can't compare offset-naive
    and offset-aware datetimes` on every test that made a second
    authenticated request after login (i.e. anything that exercised the
    sliding-expiry read path). This is the third time this exact SQLite/
    Postgres divergence has bitten a `datetime` comparison this sprint
    (budget guard, workflow engine, now sessions) — worth flagging for
    Sprint 10+ as a candidate for a single shared `_ensure_aware()`
    helper instead of the pattern being copy-pasted a fourth time.
157. **`realtime/routes.py`'s `/stream` (SSE) endpoint gained `session_
    factory` and `user` dependencies in addition to the existing `event_
    bus`, and checks `project_owned_by` before calling `event_bus.
    register_stream`.** The brief's own §2.4 flags SSE explicitly ("쿠키가
    자동 전송되므로 동작하지만, 반드시 테스트로 확인해라") because `EventSource`
    can't set custom headers — auth here only works *because* it's a
    cookie, confirming the Sprint 9 §2.1 cookie-over-JWT choice was load-
    bearing for this specific route, not just a general preference.
    Covered by `test_sse_stream_requires_auth` (401) and `test_sse_
    stream_cross_account_returns_404` (404) in `tests/test_auth.py`.
158. **`tests/conftest.py`'s new `api_client` fixture deliberately does
    not override `get_current_user`**, unlike every other dependency
    (`get_session_factory`, `get_event_bus`, etc., which read `request.
    app.state.X` and only get populated by `main.py`'s real `lifespan`).
    Every prior test in this codebase exercised the service layer
    directly and never touched an HTTP route, so nothing previously
    verified that a 401 or a cross-account 404 actually reaches the
    client over real cookies. `api_client` wires a real `httpx.
    AsyncClient` against the real FastAPI `app` via `ASGITransport`,
    overriding only the *infra* singletons with the harness's own (no
    Postgres/Docker needed), while leaving auth resolution — cookie in,
    session lookup, `UserORM` out — running for real. `httpx`'s built-in
    cookie jar persisting `Set-Cookie` across requests on the same client
    instance is what makes the register→cookie→authenticated-request and
    login→logout→401 flows testable in a handful of lines each.

### Phase 4 — Frontend auth
159. **`AuthProvider` is a plain React Context, not a TanStack Query
    hook**, deliberately matching `RealtimeProvider`'s existing pattern
    rather than adding a state library for one value. `lib/api.ts`
    (no React/router dependency) dispatches a `window` event on any 401;
    `AuthProvider` is the sole listener and owns the redirect, so every
    request path in the app — not just ones a page explicitly guards —
    gets the same "session gone -> back to /login" behavior for free.
160. **`AccountBadge` is a single click-to-sign-out circular initial
    button, not a dropdown**, per the brief's explicit §2.11 constraint
    ("드롭다운 메뉴 같은 건 만들지 마라"). The separate sidebar-footer email +
    "Sign out" text button (also brief-specified, "로그아웃 버튼 (사이드바
    하단)") is the second, distinct affordance — the two aren't meant to
    be collapsed into one control.
161. **Phase 4 manual verification ran against a throwaway SQLite DB, not
    Postgres**, because Docker Desktop's daemon wasn't running in this
    session (same constraint noted in DECISIONS.md #153 for the Alembic
    migration check). `config.py` already documents sqlite+aiosqlite as
    the supported zero-dependency fallback for "quick local runs", so
    this is within the architecture's own stated allowances, not a
    workaround. Booted the real API (`uvicorn`) and real dashboard dev
    server, then drove the actual cookie-based flow with `curl` end to
    end: register -> `/me` succeeds -> `/me` without cookie is 401 ->
    logout -> `/me` is 401 -> login -> `/me` succeeds again. No headless
    browser tool is available in this environment, so the visual
    click-through was not captured; SSR HTML output was checked instead
    to confirm the login page renders real `type="email"`/`type=
    "password"` inputs with the expected copy. Flagging this gap
    explicitly rather than silently calling it "browser-tested" — a
    true click-through (and the Postgres migration path from #153)
    should be re-run in Phase 5 or Sprint 10 if a machine with Docker
    running becomes available.

### Phase 5 — Verification found a real Phase 1 bug

162. **`recover_orphaned_tasks()` reset the orphaned `TaskORM` row but
    never touched the `AgentORM` row working it** — found live during
    Phase 5's DoD-2 manual test, not from reading code. Repro: create a
    mission, assign it (PM goes idle -> ... -> working), kill the API
    process mid-pipeline (DoD item 1's own scenario), restart. The boot
    sweep correctly moved the task to `blocked`, but the PM's
    `AgentState` stayed `working` forever — nothing in the system ever
    transitions an agent out of a busy state except the pipeline
    coroutine that just died. The next mission ever assigned to that
    same Employee then crashed the whole pipeline with
    `InvalidTransition: <AgentState.WORKING> -> <AgentState.ASSIGNED> is
    not an allowed transition` (`workflow_engine/engine.py`'s `_run_role`
    unconditionally transitions to `ASSIGNED` at stage start). This is
    exactly the kind of gap the brief's Appendix B asks to be surfaced,
    not hidden: Phase 1's own DoD item 1 only ever asserted on Task
    state, so the automated tests passed while the live behavior was
    still broken for a second mission. **Fix:** `recover_orphaned_tasks()`
    now also queries `AgentORM` rows whose `current_task_id` matches a
    just-recovered task, and walks each one back to `idle` through
    `AGENT_TRANSITIONS` (validated hop-by-hop via the real `transition()`
    state machine, same as the existing Task side) —
    `WORKING/PLANNING/ASSIGNED/BLOCKED -> FAILED -> IDLE`, or
    `WAITING_REVIEW -> BLOCKED -> FAILED -> IDLE`. `FAILED` was chosen as
    the narrated intermediate because "the work never finished" is
    honest CEO-legible framing, matching how a normal pipeline failure
    already reads on the Timeline. One `AgentStateChanged` event is
    published per freed Employee (not one per hop), so the Timeline
    reads as a single recovery action, not simulated multi-step churn.
    Added three tests to `tests/test_reliability.py`
    (`test_recover_orphaned_tasks_frees_stuck_agent`,
    `_leaves_idle_agents_untouched`, `_emits_agent_state_changed_event`);
    full suite re-run at 194 passed / 4 skipped (was 191/4 before this
    fix's 3 new tests). Re-verified live end-to-end against the running
    mock-provider server: killed it mid-mission, restarted, confirmed
    the Employee returned to `idle` with `current_task_id` cleared via
    direct SQLite inspection, then successfully ran a brand-new mission
    through the same Employee to full `completed` with no crash and no
    traceback in the server log.

## Sprint 10 — Phase B: Role / Employee separation

### Phase 0 — Diagnosability + Sprint 9 followups

163. **Toast system built from scratch instead of pulling in a library** —
    no toast/notification primitive existed anywhere in
    `apps/dashboard`, and Rule #18 ("CEO actions never fail silently")
    requires every one of the ~12 `useMutation` hooks in `lib/hooks.ts`
    to surface failures visibly. Rather than add a dependency for a
    ~60-line component, added `components/ToastProvider.tsx`: a
    `ToastProvider` (mounted once in `app/providers.tsx`, inside
    `QueryClientProvider` and outside `AuthProvider` so any auth-flow
    mutation can also use it) exposing `useToast().showToast(message)`,
    plus a `mutationErrorMessage(error)` helper that unwraps
    `ApiError.message` (already the FastAPI `detail` string, CEO-legible
    per existing convention) with a generic fallback for network
    failures. Every mutation hook in `lib/hooks.ts` now has an `onError`
    calling `showToast(mutationErrorMessage(error))` — this fires
    regardless of whether the call site uses `.mutate()` or
    `.mutateAsync()`, so components that `await mutateAsync(...)` in a
    try-less `async function` (several pre-existing forms did this,
    e.g. `EmployeeProfile.tsx`, `NewMissionForm.tsx`,
    `app/company/[id]/settings/page.tsx`) still get a visible toast on
    failure even though the awaited promise itself goes unhandled past
    the component (a console-only artifact, not a UI gap — the CEO
    already saw the toast). Toasts auto-dismiss after 7s or on click;
    styled with the existing `status-red`/`status-green` Tailwind
    tokens rather than inventing new colors.

164. **Cancel-button visibility mirrors `TASK_TRANSITIONS` exactly,
    rather than allowlisting specific "in-progress" states** — the
    brief said "visible only on in-progress missions." Backend
    `TASK_TRANSITIONS` (`core/lifecycle/task_states.py`) already encodes
    the real rule: every state has a path to `CANCELLED` except
    `COMPLETED`, `CANCELLED`, and `BLOCKED` (empty transition sets).
    Duplicating that as a frontend allowlist of "in-progress" states
    would drift the moment a new state is added on the backend.
    Instead, `MissionDetail.tsx` uses one `NOT_CANCELLABLE_STATES` set
    matching those three terminal states, shown as a "Cancel Mission"
    button with a confirm/never-mind inline step (no browser
    `window.confirm`, to match the app's existing dialog-free style)
    that calls the new `useCancelMission` hook
    (`api.cancelMission` -> `POST /api/tasks/{id}/cancel`, matching the
    existing `TaskCancelRequest{reason}` contract exactly). It renders
    alongside the "Assign to Department" button (not mutually
    exclusive) since a `created` mission is itself cancellable per the
    same transition table.

### Phase 1 — RoleSpec as first-class data

165. **`RoleSpec.default_profile` is a computed `@property`, not a stored
    dataclass field** — the brief's illustrative `RoleSpec` sketch
    (§6) shows `default_profile` as a plain field, but storing a second
    copy of `founding_name`/`key` inside a `default_profile` dict would
    itself be the "duplicate Role source" §7 explicitly forbids, and a
    stored `Mapping` field on a frozen dataclass is still a mutable
    object underneath unless deliberately wrapped. Implemented instead
    as `@property def default_profile(self) -> Mapping[str, str]: return
    MappingProxyType({"name": self.founding_name, "role": self.key})` --
    every read derives fresh from the two already-canonical fields, and
    `MappingProxyType` makes the returned view read-only (`TypeError` on
    item assignment) without needing a `frozen`-dict library or a
    `copy.deepcopy` on every access. Call sites construct the real,
    mutable-by-design `AgentProfile` only at the point of use:
    `AgentProfile(**role.default_profile)` (`agent_runtime/service.py`
    `create_department`, and `tests/test_template.py`'s founding-profile
    assertion). This also fully removed the `TEMPLATE.default_profiles`,
    `TEMPLATE.role_contracts`, and `TEMPLATE.model_ref_for_role`
    module-level dicts (Sprint 4.7/9 leftovers that duplicated
    `RoleSpec.model_ref`/`.contract`/founding identity as second dicts
    keyed by role string) -- five consumer files
    (`agent_runtime/service.py`, `agent_profiles/service.py`,
    `tasks/service.py`, `workflow_engine/engine.py`,
    `prompt_builder/role_contracts.py`) now read `TEMPLATE.roles_by_key[
    key].model_ref` / `.contract` directly, or (for `role_contracts.py`'s
    public `ROLE_CONTRACTS` dict, still depended on by `builder.py` and
    `tests/test_prompt_builder.py`) rebuild it as a one-line
    comprehension over `TEMPLATE.roles` at import time rather than
    proxying a `TEMPLATE` field. `RoleSpec` gained
    `category: Literal["leadership","worker"]`, `singleton: bool`,
    `harness: Literal["one_shot"]`, `tools: tuple[str,...]` (empty for
    every role this sprint -- grant structure only, no real tool grants
    until a later sprint per Rule #12), and `permissions: tuple[str,...]`
    (organizational-action declarations, e.g. `"assign_mission"` for PM,
    `"produce_deliverable"` for Engineer, `"request_ceo_decision"` for
    PM/Reviewer -- declared as data this sprint, not yet enforced
    anywhere; enforcement is Sprint 12+ per the brief). PM and Reviewer
    are `category="leadership", singleton=True`; Engineer is
    `category="worker", singleton=False`, matching CLAUDE.md §2.3's
    leadership/worker split (singleton *enforcement* at the service
    layer is Phase 2 scope, not this phase). Five new tests added to
    `tests/test_template.py` cover: `RoleSpec` frozen-ness
    (`dataclasses.FrozenInstanceError` on attribute assignment),
    leadership-vs-worker singleton flags, absence of the three deleted
    duplicate dicts on `TEMPLATE` (`hasattr` checks), `default_profile`
    read-only-ness (`TypeError` on item assignment) and value
    correctness, and that `default_profile` is genuinely derived (two
    `RoleSpec`s built with the same identity fields via
    `dataclasses.replace` produce equal `default_profile`s). Full suite:
    199 passed, 4 skipped (was 194/4 before this phase's 5 new tests).

### Phase 2 — Employee schema (`role_key`, singleton enforcement)

166. **`AgentORM.role` renamed to `role_key` via a pure Alembic rename
    (`batch_alter_table`, no data loss), scoped to `AgentORM` only** —
    brief §9.1 asks specifically for `agents.role` -> `agents.role_key`
    so the column visibly references `RoleSpec.key` rather than reading
    as an arbitrary string. `CostEntryORM.role` was deliberately left
    unrenamed: it's a write-only telemetry snapshot (never filtered or
    joined on anywhere in `costs/service.py`), the brief's §9.1 text
    names only `AgentORM`, and renaming it would be scope creep with no
    behavioral or architectural payoff this sprint. The external JSON
    contract and event payloads were kept byte-identical (CLAUDE.md's
    "동작 변화 0" applies) by giving `AgentResponse.role` a Pydantic v2
    `Field(validation_alias="role_key")` (works with
    `from_attributes=True`) rather than renaming the API field, and by
    reading `row.role_key` into event payloads/reasons that still use the
    literal `"role"` JSON key. Migration verified by running the full
    chain (`baseline -> accounts_and_sessions -> agent_role_key_rename`)
    against a scratch SQLite DB, then `downgrade -1` followed by
    `upgrade head` again, to confirm both directions of
    `batch_alter_table` work before relying on it against Postgres.
    167. **`create_employee()` singleton enforcement is a service-layer
    check-then-insert, not a DB-level unique constraint** — brief §10
    requires either a DB constraint or a documented reason a
    service-layer check is sufficient. Chose the service-layer check
    (`SingletonRoleViolation` raised inside `create_employee` when
    `role.singleton` is true and a row with that `project_id`/`role_key`
    already exists) because: (a) `create_employee` is not wired to any
    route this sprint -- Sprint 11 adds the hiring endpoint, so the
    function is unreachable from any concurrent HTTP request path today,
    making a TOCTOU race a theoretical, not live, concern; (b) a
    conditional/partial unique index (unique only when
    `RoleSpec.singleton` is true) can't be expressed as a plain column
    constraint since `singleton` is template data, not a DB-resident
    flag, and a real fix would need either a generated/trigger-backed
    column or an application-level advisory lock -- both meaningfully
    more machinery than this sprint's actual reachable surface
    justifies (CLAUDE.md §16.3, "불필요한 과설계는 하지 않는다"); (c)
    "single worker assumptions" is already a logged accepted tradeoff
    (CLAUDE.md §15). Revisit when Sprint 11 adds the hiring route and a
    concurrent "click Hire twice" scenario becomes real. Five new tests
    in `tests/test_employee_singleton.py` cover: `AgentORM.role_key`
    (not `.role`) is what founding rows expose; a second PM and a second
    Reviewer both raise `SingletonRoleViolation`; two additional Engineer
    Employees are both accepted (three total Engineers on one project);
    and a rejected second-PM attempt leaves exactly one PM row behind
    (no partial insert). `workflow_engine/engine.py`'s `_agents_for`
    was changed to return `dict[str, list[AgentORM]]` (grouped by
    `role_key`) instead of `dict[str, AgentORM]`, removing the
    structural one-employee-per-role assumption at the query layer; the
    pipeline call site still picks `agents[stage.role_key][0]`
    (behaviorally identical today, since no route yet creates a second
    worker Employee) with a comment marking it for replacement by
    Phase 3's `resolve_employee_for_role`. Full suite: 204 passed, 4
    skipped (199/4 after Phase 1, plus this phase's 5 new tests).

### Phase 3 — Role -> Employee resolution

168. **`resolve_employee_for_role` lives in a new
    `workflow_engine/employee_resolution.py`, as a pure function over a
    list of `AgentORM`, not a method on the engine** — brief §12 requires
    the selection *rule* to live in exactly one place so Sprint 12 can
    swap it for the PM's explicit assignment without touching engine
    call sites. Keeping it a free function with no DB/event-bus
    dependency makes the rule itself trivially unit-testable (5 of the 7
    new tests in `tests/test_employee_resolution.py` construct
    `AgentORM` instances directly, no `harness` fixture needed) while
    the engine's new `_resolve_agent` wrapper method owns the two side
    effects the pure rule can't: persisting `last_assigned_at` and
    publishing `AGENT_RESOLVED`. §12.1's fixed rule for this sprint --
    idle Employees first, then whoever has gone longest without being
    assigned, falling back to the whole Role if nobody's idle -- reduces
    to `min()` over a tie-break key once a "never assigned" Employee is
    defined as waiting longer than any real timestamp.
    169. **A new nullable `AgentORM.last_assigned_at` column, set by the
    resolver itself, not derived from `current_task_id`** — §13 requires
    a deterministic tie-break field, and no existing column answers "when
    was this Employee last picked": `current_task_id` is cleared back to
    `None` the moment a Mission finishes, so it can't be read after the
    fact, and repurposing it would conflate "currently busy" with "was
    once chosen." Added via a second pure-rename-shaped migration
    (`3c792f42c404`, nullable `add_column`/`drop_column` via
    `batch_alter_table`, chained after Phase 2's `role_key` rename;
    verified upgrade -> downgrade -> upgrade against a scratch SQLite DB
    the same way as Phase 2's migration). NULL means "never resolved by
    this selection layer" and deliberately sorts as the oldest possible
    value, so every pre-Sprint-10 Employee is eligible first on upgrade
    rather than being starved by a synthetic non-NULL default. The
    tie-break tuple is `(has_been_assigned, last_assigned_at or
    created_at, created_at, id)` rather than comparing against a
    synthetic `datetime.min` sentinel -- SQLite returns naive datetimes
    for `DateTime(timezone=True)` columns (verified empirically) while
    Postgres returns aware ones, so a hand-built sentinel would need two
    different tz-handling branches to compare safely against both;
    comparing only real, same-column values already sidesteps the whole
    issue. §14's observability requirement (role, who, when, why) is met
    without adding a `resolved_at` payload field: `Event.created_at` is
    already the "when," and `Event.reason` carries the "why" in prose
    (e.g. `"Resolved engineer to Priya Shah (was idle, longest since
    assigned)"`); the payload itself (`role_key`, `agent_id`, `rule:
    "idle" | "no_idle_fallback"`) keeps just the two machine-readable
    facts a future UI would filter/group on. No dedicated "test-only
    multi-employee template" (brief item 3.4) was built as a second
    `CompanyTemplate` -- Engineer was already `singleton=False` since
    Phase 1, so `create_employee(session_factory, project_id,
    "engineer")` against the *existing* `software_company` template is
    sufficient to produce a real multi-Employee Role for tests; a second
    template would duplicate Sprint 10's actual template shape for no
    behavioral gain (CLAUDE.md §16.3). Full suite: 211 passed, 4 skipped
    (204/4 after Phase 2, plus this phase's 7 new tests).

### Phase 4 — #16 enforcement + UI

170. **Added a real `RoleSpec.description: str` field rather than reusing
    `intro` for the Roles API (brief §18)** — `intro` is a first-person
    onboarding line spoken as a founding conversation event ("Hi, I'm
    Priya, your PM..."), not a third-person position summary suitable for
    a CEO-facing role list; reusing it would leak onboarding voice/tense
    into an API meant to describe the *position*, not introduce the
    person occupying it. `description` is populated for all three
    existing Roles and is a required field like every other `RoleSpec`
    attribute, so a future Role (Sprint 11's CTO) cannot be added without
    also supplying one.
171. **The Rule #16 guard (brief §17) is an AST walk over `app/`, registered
    as `tests/test_role_hardcoding_guard.py` so it runs under `make
    test`/pytest rather than as a separate script** — the brief explicitly
    warns a substring search (`"engineer" not in source`) false-positives
    on comments/docstrings/fixtures/log text. The guard instead parses
    every `.py` file under `app/` (except `app/templates/`, the one place
    Rule #16 permits role-name constants, since that's the template
    *assembling its own data*) and flags three concrete AST shapes: (a) an
    `ast.Compare` with `==`/`!=` against a string constant that is a real
    role key -- "role-specific behavioral branch"; (b) an `ast.Compare`
    with `in`/`not in` against a literal list/tuple/set of role-key
    constants -- same category; (c) an `ast.Subscript` that either indexes
    a "roles"-named collection by integer position ("position-based
    access") or indexes any mapping with a literal role-key string
    ("hardcoded role dependency"). The set of "real role keys" is read
    from the live `TEMPLATE.roles_by_key`, not hand-copied into the test,
    so the guard automatically covers a role the template adds later. A
    companion test (`test_the_guard_actually_detects_a_real_violation`)
    feeds the checker four inline snippets shaped exactly like CLAUDE.md's
    forbidden-pattern examples and asserts each one is caught -- proving
    the guard actually fires rather than vacuously passing. Confirmed
    empirically that `prompt_builder/builder.py`'s `if role ==
    ENGINEER_ROLE_KEY:` does *not* trip the guard: `ENGINEER_ROLE_KEY` is
    a module-level value derived via `first_stage_role_key(TEMPLATE.pipeline,
    "produce")` (a Sprint 9 pattern CLAUDE.md's Rule #16 explicitly
    permits, "stage kinds... are allowed to drive behavior"), not a
    string literal in the `Compare` node itself, so the AST shape the
    guard looks for genuinely isn't present.
172. **`SituationReport.tsx`'s `employees?.find((e) => e.role === "pm")` was
    kept, not rewritten to be data-driven** — Rule #11 ("the CEO has
    exactly one conversational counterpart: the PM") makes the PM's
    identity a fixed architectural invariant, not Role data a future
    template could reassign; the Situation Report is specifically framed
    as spoken in the PM's voice, so this lookup is finding *the* CEO
    counterpart Rule #11 already hardwires, not branching on a swappable
    worker Role. There is also no data-driven way to do this today without
    widening scope: the Roles API deliberately excludes `permissions`
    (§18), which is the only field that would otherwise distinguish PM
    from the other `category: "leadership"` singleton (Reviewer) without a
    literal role-key string. Revisit only if a later sprint exposes an
    explicit "CEO counterpart" flag.
173. **Frontend Rule #16 cleanup**: `Agent.role` narrowed from a hardcoded
    `"pm" | "engineer" | "reviewer"` union to `string` (a closed union
    silently breaks the moment Sprint 11 adds a `"cto"` role key, which is
    exactly the kind of engine-adjacent hardcoding #16 targets even though
    it's a type annotation, not a runtime branch); `lib/utils.ts`'s
    `ROLE_LABEL`/`roleLabel()` static lookup table was replaced with a
    `roleLabel(roles, roleKey)` that reads `title` from the new Roles API
    response, added via a new `useRoles()` hook. The Employees page
    (`app/company/[id]/employees/page.tsx`) was rewritten per brief §19 /
    UX_SPEC §5.4 to group Employees by `Role.category` (Leadership first,
    then Engineering) with a per-Role subheading listing every Employee
    currently holding that Role -- the section-heading copy
    (`{leadership: "Leadership", worker: "Engineering"}`) is UI text keyed
    off the two `category` enum values the API returns, not a per-Role
    hardcode, and a category section only renders once it actually holds
    a hired Employee (hidden means absent, §10.4). No "+ Add Employee"
    affordance was built (out of scope this sprint per brief §19); the
    existing Employee profile-edit page/flow is untouched aside from its
    `roleLabel` call site. `app/company/[id]/settings/page.tsx`'s own
    `ROLE_LABEL = { planner: "PM", builder: "Engineer", reviewer:
    "Reviewer" }` was left as-is -- it labels `model_registry`'s
    "planner"/"builder"/"reviewer" model-slot vocabulary (a distinct,
    pre-existing axis for per-function AI model overrides, unrelated to
    `RoleSpec.key`), not an organizational Role identity, so it's outside
    this phase's scope. `pnpm typecheck` and `pnpm build` both pass.

### Phase 5 — Verification, docs sync, sprint close

174. **Task creation and task assignment are two separate calls, confirmed
    correct during Phase 5's own E2E verification, not a bug** —
    `POST /projects/{id}/tasks` only inserts the row and publishes
    `TASK_CREATED` (nobody subscribes to it; it's audit-log only).
    `workflow_engine.start_task` is only reached through
    `POST /tasks/{id}/assign` (`tasks/service.py`'s `assign_task`, which
    transitions `CREATED -> ASSIGNED` then calls `start_task`). A first
    verification pass created a mission and polled it for 2.5 minutes
    expecting auto-progression, saw `created` never move, and initially
    read that as a regression from this sprint's `role_key` rename before
    tracing the actual call graph -- it is unrelated, pre-existing
    behavior (a CEO creating a Mission and a CEO assigning it are
    deliberately distinct actions in the org model, §2.2). Noted here so
    a future sprint's verification pass doesn't re-diagnose the same
    non-bug.
175. **Full mission lifecycle re-verified end-to-end against a live
    mock-provider server after Phase 4's changes**: register -> create
    company -> `GET /roles` (three Roles, exact `key/title/category/
    singleton/description` shape) -> `GET /agents` (founding roster keyed
    by `role_key`) -> create mission -> assign -> `in_progress -> in_review
    -> pending_approval` -> approve -> `completed` with a real mission
    branch and commit SHA. A second mission verified the cancel path:
    assign -> cancel mid-`in_progress` -> `cancelled`, Engineer's
    `AgentState` back to `idle` with `current_task_id` cleared (Sprint 9
    Phase 0.8's fix still holds under the new `role_key` schema). This is
    **API-level E2E verification** (curl against the running server), not
    browser verification -- no browser automation tool exists in this
    environment (confirmed via an explicit tool search). PROGRESS.txt
    5.4/5.5 are marked accordingly rather than claiming a browser check
    that wasn't performed (CLAUDE.md §16.7).
176. **`CLAUDE.md`'s long-pending uncommitted restructure (numbered
    sections, expanded rules #11-#18) was folded into this sprint's docs
    commit rather than left open** — it had been deliberately excluded
    from the Phase 2 and Phase 3 commits as out-of-scope-for-that-commit,
    but by Phase 5 it was reviewed in full: its content (including §2.3's
    Role/Employee table and Rule #16 itself) already matches what this
    sprint built, so no rewrite was needed, only two accuracy fixes --
    the Sprint 10 roadmap row marked shipped, and §2.3's tag changed from
    "not built" to "structural separation shipped" with a note that
    CTO/hiring remain Sprint 11. Folding it in avoids a second, unrelated
    multi-hundred-line diff landing on top of whatever Sprint 11 touches
    in the same file.
177. **Full suite re-run at sprint close: 218 passed, 4 skipped** (was 194
    at Sprint 9 close; +24 net this sprint across Phases 1-4 -- RoleSpec/
    template tests, `role_key` migration + singleton tests, resolver
    tests, Roles API tests, and the Rule #16 guard's 5 tests). Dashboard
    `pnpm typecheck` and `pnpm build` both clean, 15 routes compiling.
    Zero pre-existing test assertions changed behavior -- the 6 touched
    test files are mechanical `AgentORM.role -> role_key` fixture renames
    plus additive new tests, matching the brief's "동작 변화 0" requirement
    (§21).

## Sprint 11 — Build the Company: CTO, Hiring, Employee Configuration

### Phase 1 — CTO RoleSpec and canonical configuration data

178. **CTO is a vacant, hireable Role at founding, not auto-seeded** — added
    `RoleSpec.founding: bool = True` rather than a second engine-owned
    founding-roster list. `create_department` now filters
    `TEMPLATE.roles` by `role.founding` instead of iterating every Role,
    which stays Rule #16-compliant (a data attribute check, not a role-key
    branch) and requires zero engine changes. CTO is the only Role with
    `founding=False`; PM/Engineer/Reviewer keep their existing founding
    behavior byte-for-byte (verified by
    `test_founding_matches_the_template_exactly` and
    `test_founding_posts_an_intro_conversation_event_per_employee`, both
    updated to filter by `role.founding` -- classified as intentional
    behavior change per the brief's testing-discipline categories, not
    implementation-detail coupling). This satisfies brief §6.9's stated
    preference (CTO "visibly available to hire rather than silently
    auto-hired") without inventing a parallel founding-roster concept.
179. **CTO reuses the `"planner-default"` model_registry slot rather than
    introducing a new one** — `model_registry`'s role vocabulary
    (`planner`/`builder`/`reviewer`) is a distinct axis from `RoleSpec.key`,
    and CTO has no pipeline stage this sprint (no PM<->CTO planning yet,
    brief §4.1/§9), so nothing would ever resolve a `"cto-default"` ref.
    Adding an unused registry slot would be speculative scope the brief
    explicitly warns against ("do not enlarge... merely because a cleaner
    theoretical design exists," CLAUDE.md §16.3). Reusing `planner-default`
    costs nothing today (CTO's model choice in the hiring form comes from
    `options_for_role(provider, "planner")`, same list the CEO already
    sees for PM) and is a one-line change to introduce a real `cto-default`
    slot the day CTO actually joins a pipeline stage.
180. **Skill templates are a new, minimal, presentation-only registry**
    (`app/modules/skill_templates/`) — three entries (`generalist`,
    `research_focused`, `speed_focused`), frozen dataclass, each carrying
    an inert `capabilities: tuple[str, ...]` field deliberately excluded
    from the public API response (only `key`/`title`/`description` are
    exposed, mirroring the Roles API's own `contract`/`tools`/
    `permissions` exclusion). No skill template grants any runtime
    capability yet -- `RoleSpec.tools` remains the only whitelist that
    would ever do that (currently empty for every Role), so selecting a
    skill template today only changes what displays on an Employee, never
    what it can execute. This keeps Sprint 11 clearly on the presentation
    side of the Sprint 16 Agent Harness boundary the brief draws (§4.6).

### Phase 2 — Persistence and atomic hiring

181. **No new `AgentORM` columns for per-Employee model/skill
    configuration** — re-reading the existing `RoutedProviderGateway`
    revealed a three-tier model resolution already in production
    (`AgentProfile.model_ref` > per-role CEO override via `settings_kv` >
    registry default), so an Employee-level model override already has a
    home. `skill_template_key` follows the same pattern: one new field on
    the existing `AgentProfile` Pydantic model, persisted inside the JSON
    `agents.profile` blob it already occupies. The *only* schema change
    Phase 2 actually required was the new `role_singleton_locks` table --
    not the AgentORM column additions assumed before re-reading the
    provider gateway. Smaller diff, same guarantees, no migration needed
    for configuration data at all (brief §6.2/§10.1's "smallest coherent
    schema change").
182. **Atomic singleton enforcement via a composite-primary-key lock
    table, not `SELECT ... FOR UPDATE` or a partial unique index** — a new
    `role_singleton_locks` table keyed on `(project_id, role_key)` is
    inserted in the same transaction as the Employee row whenever
    `role.singleton` is True. Two concurrent `hire_employee` calls for the
    same Role now race on the database's own primary-key uniqueness
    constraint, not application logic; the loser's `IntegrityError` is
    caught and converted to `SingletonRoleViolation`. Rejected
    alternatives: `SELECT FOR UPDATE` on the Employee table would still
    need something to lock *before* any row for the Role exists yet (the
    common case), which a plain row lock can't do; a Postgres partial
    unique index (`WHERE role_key IN ('pm','reviewer')`) would hardcode
    singleton role keys into a migration, violating Rule #16's "no
    hardcoded role identity" spirit and silently failing to protect a
    *future* singleton Role added only to the template. The lock table
    instead derives its protection from `RoleSpec.singleton`, so a new
    singleton Role added purely as template data is protected with zero
    engine changes.
183. **Founding PM/Reviewer must also claim a lock row, in the same
    transaction as their founding insert** — `DBAgentRuntime.
    create_department()` was extended to add a `RoleSingletonLockORM` row
    for every founding Role with `singleton=True`, not just `hire_employee`.
    Missing this would have left a live gap: a freshly founded company's
    PM/Reviewer would hold no lock row, so the *first* `hire_employee`
    call for `"pm"` afterward would find no conflicting lock and insert a
    second PM straight past the guarantee this phase exists to build.
    Caught by re-reading `create_department` against the new invariant
    before writing tests, not by a failing test -- recorded here so the
    reasoning survives even though no regression test could have caught
    the *absence* of this fix without first asserting the invariant it
    protects.
184. **SQLite concurrency test needs an explicit busy timeout; Postgres
    needs none** — the real concurrency test
    (`test_hire_employee_concurrent_hires_for_a_singleton_role_only_one_wins`)
    fires two `hire_employee` calls via `asyncio.gather` against a
    dedicated SQLite engine with `connect_args={"timeout": 5}`. SQLite
    serializes writers at the file-lock level (not Postgres's row-level
    MVCC), so without a busy timeout the losing writer would surface an
    unrelated `OperationalError: database is locked` instead of the
    `IntegrityError` the composite primary key is supposed to produce;
    `timeout` makes the second writer block-and-retry until the first
    transaction commits, so the loser reaches the PK conflict cleanly.
    This is a test-harness concern only -- the production Postgres
    container needs no equivalent setting, since row-level MVCC lets both
    transactions proceed until one hits the real conflict. Verified
    directly against the live `commander-postgres-1` container this
    sprint: `alembic upgrade head` / `downgrade -1` / `upgrade head` all
    ran cleanly, and the backfill correctly seeded one lock row per
    pre-existing PM/Reviewer across every project in the dev database.
185. **Employee renaming after hire is out of scope this sprint** — the
    brief's wording on Employee update is conditional ("if the existing
    naming model permits it"). `AgentORM.name` (a top-level column, used
    for FK-free display and query filters) and `AgentProfile.name` (a
    field inside the JSON `profile` blob) are two copies of the same
    fact with no existing atomic-sync path between them; building one
    is a real feature, not something to fold silently into "extend the
    profile PUT endpoint." Name is therefore settable only at hire time
    via `hire_employee`; `PUT /api/agents/{id}/profile` continues to
    reject `name` (it was never in `ProfileUpdateRequest`). Revisit if a
    later sprint brief asks for it explicitly.
186. **Reused two existing endpoints instead of building duplicates** --
    `PUT /api/agents/{agent_id}/profile` (extended with
    `skill_template_key`, mirroring its existing `model_ref` validation
    block) covers post-hire Employee configuration, and
    `GET /api/projects/{project_id}/models` (unchanged) remains the one
    model catalog the hiring form's Model dropdown reads from. `RoleResponse`
    gained a `model_ref` field so the dashboard can derive
    `model_ref.removesuffix("-default")` and call the existing models
    endpoint with the right registry-role, without a second, parallel
    model-options endpoint keyed by `role_key` instead of the registry's
    own vocabulary. Satisfies brief §6.6 ("prefer extending existing
    endpoints over creating duplicate representations") directly.

### Phase 3 — API and runtime integration (retroactive note)

187. **No separate Phase 3 decision log exists because Phase 2 and Phase 3
    shipped as one commit** (`3f8d3f4`, "atomic CTO/Employee hiring with
    DB-backed singleton locks") -- `hire_employee`'s persistence/atomicity
    work (Phase 2) and its route/schema exposure (Phase 3:
    `POST /api/projects/{id}/agents`, `RoleResponse.model_ref`, the
    `agents`/`skill-templates` route wiring) were implemented and reasoned
    about together, since the service was built route-first (the route
    signature drove what the service needed to validate and return).
    Decision #186 above, in particular, *is* a Phase 3 (API surface)
    decision despite sitting under the Phase 2 heading. Recorded here
    during Phase 5's documentation audit (brief §8 step 15/§13) so the
    absence of a dedicated "### Phase 3" heading reads as a deliberate
    accounting choice, not a gap the sprint forgot to document.

### Phase 4 — Dashboard hiring and configuration UX

188. **Occupied singleton Roles stay visible and disabled in the Hire form,
    labeled "(already hired)", rather than being filtered out of the
    `<select>`** (`NewEmployeeForm.tsx`) -- CLAUDE.md Rule #18 forbids a
    CEO action from appearing to do nothing without explanation; an option
    that silently disappeared once PM/Reviewer/CTO were hired would look
    like a bug (or make the CEO wonder whether the Role was ever real),
    not read as "this position is filled." The effective Role selection
    still auto-advances to the first *hireable* Role
    (`hireableRoles[0]`) so the common case (hiring into an open worker
    Role) never requires the CEO to click past a disabled option first.
189. **Removed the last Rule #16-risk frontend map** -- `EmployeeProfile.tsx`
    previously hardcoded a `MODEL_ROLE_FOR_AGENT_ROLE` object mapping
    `role_key` string literals (`"pm"`, `"engineer"`, `"reviewer"`) to
    model-registry roles (`"planner"`, `"builder"`, `"reviewer"`) so the
    model-override dropdown knew which model catalog to read. Adding `cto`
    would have required editing this map by hand, which is exactly the
    "adding a Role requires an engine/component change" pattern Rule #16
    forbids for backend code and that the Sprint 10 AST guard cannot see
    (the guard only scans `apps/api/`, not the dashboard). Fixed by adding
    `RoleResponse.model_ref` (decision #186) and a small derivation helper,
    `registryRoleFor(roles, roleKey)` (`lib/utils.ts`), used identically by
    both `EmployeeProfile.tsx` and `NewEmployeeForm.tsx`. No dashboard code
    change is required for CTO or any future Role.
190. **Model/skill-template dropdowns default to "Use company default" /
    "Default" (empty string), never a pre-selected concrete value** -- for
    both the hire form and the edit form, submitting with the default
    selection sends `null`/omitted `model_ref` and lets the server's
    3-tier resolution or `DEFAULT_SKILL_TEMPLATE_KEY` apply, rather than
    the frontend guessing and hardcoding a "first option" default. Keeps
    the default policy server-owned (brief §4.5), consistent with why
    `RoleResponse.model_ref` and the skill-template registry exist as
    server data in the first place.

### Phase 5 — Regression, security, documentation (findings)

191. **No implementation bugs found during Phase 5 audit** -- the full
    regression pass (248 passed / 4 skipped, dashboard typecheck + build
    clean, live-Postgres migration upgrade-from-Sprint-10 and fresh-bootstrap
    both verified, AST role-hardcoding guard green, manual read-through of
    every new route/schema/event payload/mutation hook) found zero auth,
    ownership, secret-leakage, hardcoding, or silent-failure defects.
    Nothing required a code fix in Phase 5; the work was verification and
    documentation sync only, exactly as the brief scopes it (§8 Phase 5,
    "regression/audit/docs only").
192. **`WorkflowEngine` received zero Sprint 11 changes** -- confirmed by an
    empty `git diff --stat` for `apps/api/app/modules/workflow_engine`
    across the entire sprint (`29fd400..HEAD`). Hiring/configuration logic
    lives entirely in `agent_runtime`/`agent_profiles`/`skill_templates`,
    as the brief's constraint #14 requires; there was never a design that
    risked otherwise, so this is a confirmation, not a course-correction.
193. **Deliberate Sprint 12+ deferrals, reaffirmed at sprint close** (see
    brief §9 for the full list; recorded here as the definitive Sprint 11
    handoff boundary) -- PM↔CTO planning conversations and any CTO
    "discuss" pipeline stage; Project Specification and Requirement
    Discovery; CEO↔PM conversation/decision-authority work (Sprint 13); the
    CEO Workspace UI shell and Widget system (Sprints 14–15); the Agent
    Harness and any iterative/tool-loop execution (Sprint 16); self-
    correction (Sprint 17); Project Memory (Sprint 18); employee
    firing/removal (no safe path exists -- `role_singleton_locks` rows are
    never deleted, by design, since nothing yet frees one); the
    Backend/Frontend Engineer split and any Role beyond
    PM/CTO/Engineer/Reviewer; arbitrary Role creation, Role editing, or
    arbitrary skill/tool authoring by the CEO; a second company template;
    multi-user collaboration; and browser-tooling-dependent UI verification
    (no such tool was available in this environment for Sprint 10 or
    Sprint 11 -- re-confirmed at Phase 5 via `ToolSearch`).

## Sprint 12 — Phase C: PM<->CTO Planning + Project Specification

### Phase 0/1 — Design audit and domain layer

194. **One `SpecificationORM` aggregate covers both the planning run and the
    reviewable document**, rather than a separate "PlanningRun" and
    "Specification" pair. `status` spans both phases (draft -> planning ->
    ... -> approved/rejected/cancelled/failed); a row exists from the
    moment the CEO submits a request, long before any
    `SpecificationVersionORM` content is drafted. This directly satisfies
    brief §3's "do not introduce a duplicate aggregate without need" --
    there is exactly one thing to look up per CEO request, not two linked
    by a foreign key for no independent reason.
195. **`SpecificationORM.resume_stage`** records which orchestrator turn-kind
    to re-run once the CEO answers a clarification question (e.g.
    `"pm_analysis"`), rather than re-deriving position from turn history on
    every resume. Set only while `status=clarification_required`, cleared
    once the orchestrator resumes. Keeps resume logic a single column read
    instead of a turn-log replay.
196. **CTO gets its own `advisor-default` model_ref** (`mock-advisor-v1` in
    mock mode), replacing Sprint 11's placeholder reuse of
    `planner-default`. Reusing the PM's logical ref would have made
    `mock_provider` produce planner-shaped text for CTO planning turns --
    indistinguishable in mock mode, and semantically wrong even for real
    providers where the CTO's system prompt differs from the PM's. The
    mock-inferred label for this ref is `"advisor"`, not `"cto"` --
    `"cto"` is a real `RoleSpec.key` and comparing against it inside
    dispatch logic would trip the Rule #16 AST guard's hardcoded-role-key
    check; `"advisor"` is deliberately not a Role identity, just a model-
    voice label.
197. **A new, dedicated `POST /specifications/{id}/begin-execution`
    endpoint is the only path from an approved Specification into a
    Mission**, rather than modifying the existing generic
    `POST /projects/{id}/tasks`. The existing endpoint stays completely
    unmodified (248 pre-Sprint-12 tests exercise it) and continues to
    create ungated Missions with `specification_id = NULL`. This is the
    Sprint 12 backward-compatibility policy required by brief §4.7:
    existing/active Missions remain valid, non-code Missions are
    unaffected, and only *new code Missions created through the new
    endpoint* are gated on `spec.status == approved`. `begin-execution`
    itself does nothing but validate approval and then call the existing,
    unmodified `tasks.service.create_task`/`assign_task` -- the approval
    gate is enforced once, at the one new entry point, not by threading a
    new check through the WorkflowEngine.
198. **`prompt_builder.build()` gained one optional `contract_override`
    param**, layered in the existing traits -> custom-instructions ->
    contract-LAST order, instead of a parallel planning-specific prompt
    builder. PM/CTO planning turns pass
    `TEMPLATE.planning_contracts[role]` as the override; every other call
    site is unaffected (`contract_override=None` preserves the exact prior
    behavior). Satisfies §4.10 (planning turns still layer the Employee's
    own configured traits/custom instructions) with zero new prompt-
    assembly code paths to keep in sync.
199. **`TEMPLATE.planning_pm_role_key`/`planning_cto_role_key` are plain
    string attributes**, assigned from `PM.key`/`CTO.key` inside
    `software_company.py` itself, rather than an indexed lookup into a
    `roles`/`role_specs`-named collection. The Rule #16 structural guard
    forbids literal role-key string comparisons in engine/workflow code
    *and* flags literal integer indexing into anything named
    roles/role_specs; a plain named attribute sidesteps both concerns
    while still being template-owned data, not an engine branch.
200. **Planning turn budget: 6 turns lifetime per Specification, cumulative
    across revision rounds.** Every documented planning path (fast
    agreement, one CTO follow-up, PM clarification, CTO blocking
    feasibility) completes in 3-5 turns; turn 7 without a ready spec
    forces `status=failed`, `stop_reason="turn_limit_exceeded"`, no further
    provider calls. Chosen as the smallest bound that still lets every
    §9-required planning scenario complete without hitting the ceiling,
    per brief §4.3's "max 6 unless a lower safe bound is justified."

### Phase 2 — PM<->CTO planning orchestration

201. **No dedicated planning DI singleton -- confirmed, not just designed.**
    `PlanningOrchestrator` is built fresh per call
    (`session_factory`/`event_bus`/`agent_runtime`/`secrets`), the same
    shape `build_gateway()` already has, rather than a long-lived registry
    like `CommanderWorkflowEngine._running`. This works because every
    planning "turn burst" (`start`, `resume_after_clarification`,
    `submit_revision`) runs to completion inside one awaited call -- unlike
    a Mission's background `asyncio.Task`, nothing keeps running between
    calls, so there is nothing to track across calls. Phase 2 implementation
    confirms this held with no surprises: no cross-call state was ever
    needed.
202. **Clarification (PM) and blocking-feasibility (CTO) collapse into one
    `SpecificationStatus.CLARIFICATION_REQUIRED` stop condition**, not two
    separate statuses. Both are "planning cannot continue without CEO
    input"; the only difference is which turn kind resumes
    (`resume_stage="pm_analysis"` vs `"cto_review"`), already captured by
    the existing `resume_stage` column (#195). A second status would have
    doubled the CEO-facing API/UI surface (Phase 3/4) for a distinction the
    domain model already expresses structurally.
203. **Turn budget counts only `actor_role="employee"` rows.** The CEO's own
    clarification-answer turn is persisted as `actor_role="ceo"` and
    excluded from the `MAX_PLANNING_TURNS` count (brief §4.3's own
    definition: "a turn is one persisted PM or CTO contribution"). Counting
    the CEO's answer would silently shrink the effective PM/CTO budget by
    one every time a clarification round is used, penalizing the exact
    path the budget exists to allow.
204. **Planning turns do not call `costs.record_usage`.** Every other
    provider call site (missions, conversation replies, reports) records
    token usage; planning turns deliberately don't yet, since Sprint 12's
    scope is orchestration + domain, not a new cost-tracking dimension.
    Revisit in a later sprint if planning cost visibility becomes a CEO-
    facing requirement -- tracked here rather than silently forgotten.
205. **`SpecificationTurnORM.kind` vocabulary**: `"analysis"` (PM's initial
    read), `"review"` (CTO's feasibility pass), `"draft"` (a ready
    Specification, from either `pm_draft_or_followup` when
    `ready_to_draft=true` or the terminal `pm_draft`), `"revision"`
    (`pm_revision_draft`), `"clarification_request"` (PM's questions *or*
    CTO's blocking reason -- unified per #202), `"clarification_answer"`
    (both the CEO's resume answer, `actor_role="ceo"`, and the CTO's
    bounded in-loop follow-up answer, `actor_role="employee"` --
    distinguished by `actor_role`, not by a second kind value, since both
    are literally answers to a question raised earlier in the same turn
    sequence).
206. **The CTO's bounded follow-up (`cto_followup_answer`) never pauses for
    the CEO.** `pm_draft_or_followup` with `ready_to_draft=false` moves
    straight to `cto_followup_answer` then `pm_draft` inside the same `_run`
    loop -- it's a same-turn-burst PM<->CTO exchange, not a CEO-facing stop
    condition. Only `pm_analysis` (PM has real clarification questions) and
    `cto_review` (CTO finds the request infeasible as stated) ever produce
    `CLARIFICATION_REQUIRED`; every other turn kind is bounded, internal
    PM<->CTO back-and-forth the CEO only sees afterward as posted turns.

### Phase 3 — API, approval gate, pipeline integration

207. **`approve_specification`/`reject_specification` release
    `ActiveSpecificationLockORM` too, not just `PlanningOrchestrator`'s own
    failure/cancel paths.** `_publish_ready()` intentionally leaves the lock
    held while a Specification sits in `READY_FOR_REVIEW` (a second planning
    run must not start while one is awaiting CEO review), but approval and
    rejection are the other two ways a Specification reaches a terminal
    state, and both were found to leak the lock forever if left alone --
    the Company would permanently lose the ability to start a second
    Specification after its first was ever approved or rejected. Fixed by
    giving `planning/service.py` its own three-line `_release_lock`,
    duplicated from the orchestrator's rather than imported (Rule #1: that
    method is a private implementation detail of the turn-loop's own
    cleanup), called from both `approve_specification` and
    `reject_specification` after the state transition commits.
208. **`create_task`/`assign_task`/`TaskResponse` are re-exported through
    `tasks/__init__.py`** so `begin_execution` (Sprint 12 §4.7) can convert
    an approved Specification into a Mission through the exact same
    authoritative path every other Mission creation uses, and return the
    result through the same response contract, without reaching into
    `tasks.service`/`tasks.schemas` directly (Rule #1) or duplicating
    task-creation logic in the planning module. `tasks/routes.py`'s
    existing `POST /projects/{id}/tasks` stays byte-for-byte unmodified
    (per #197) -- only `create_task()`'s Python signature grew a
    backward-compatible `specification_id: str | None = None` parameter
    that every pre-existing caller leaves at its default.
209. **`begin_execution` validates then delegates; it does not orchestrate.**
    It checks `SpecificationStatus.APPROVED` and the one-Mission-per-
    Specification invariant (`TaskORM.specification_id` uniqueness, raising
    `SpecificationAlreadyExecutingError` on a second attempt) itself, then
    hands off unconditionally to `tasks.create_task`/`assign_task` --
    exactly the brief §5.1 boundary: the approval gate is enforced once,
    here, not threaded through `WorkflowEngine` or duplicated per call
    site.
210. **HTTP status mapping for the new planning routes**: `CTOVacantError`
    and `ActivePlanningExistsError` -> 409 (a precondition on *starting*
    planning, not a bad request body); `InvalidTransition` -> 409 across
    every state-changing route (clarification-answer, revision, approve,
    reject) -- covers double-approval/double-rejection for free since the
    second call's `transition()` raises before any write; `cancel_planning`
    returning `False` -> 409 with an explanatory detail message, mirroring
    `tasks/routes.py`'s `cancel_task` pattern exactly;
    `SpecificationAlreadyExecutingError` and the not-yet-approved
    `ValueError` from `begin_execution` both -> 409 (Mission-creation
    preconditions, not malformed input). Every route resolves ownership via
    `resource_owned_by(session_factory, SpecificationORM, ...)` or
    `project_owned_by` before calling `service`, so cross-account access is
    404 (Rule #15) before any of these domain errors can even fire.
