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
