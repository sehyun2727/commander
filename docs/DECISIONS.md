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
