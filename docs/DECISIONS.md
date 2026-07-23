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
