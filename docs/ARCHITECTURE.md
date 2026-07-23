# Commander Architecture

Version: v2.0 (As-Built)
Status: Synced with Sprint 3 implementation — 2026-07
Supersedes: v1.0 Draft (pre-implementation vision)

---

## Vision

Commander is an operating system where a solo developer becomes the CEO of an AI software company.

Users never manage prompts. Users manage a company.

Every action performed by AI must be **visible, explainable, reviewable, and replaceable**.

---

## High-Level Architecture (as built)

```text
                       Commander

                ┌─────────────────────┐
                │   CEO Dashboard      │
                │  Next.js App Router  │
                │  TanStack Query      │
                └──────┬───────▲───────┘
                       │       │
                 REST API    SSE stream
                       │       │
                       ▼       │
              ┌────────────────┴──────┐
              │  Commander API Server │
              │       (FastAPI)       │
              └──────────┬────────────┘
                         │
      ┌──────────┬───────┴──────┬─────────────┐
      ▼          ▼              ▼             ▼
 Workflow    Agent          Event Bus    Provider
  Engine     Runtime       (persist +    Gateway
      │          │          fan-out +        │
      │          │          SSE push)        ▼
      │          │              │       Model Registry
      │          │              ▼            │
      │          │          SQLite      ┌────┴─────┐
      │          │        (events,      ▼          ▼
      │          │         projects,   Mock     Anthropic
      │          │         tasks,     Provider   Provider
      │          │         agents,   (default)  (httpx)
      │          │         approvals,
      │          │         settings_kv)
```

Realtime is **SSE** (not WebSocket): one endpoint per company, replays last 50 events on connect, heartbeat every 15s, client dedups by `event.id`.

---

## Core Principle: Everything Is an Event

Every significant company action publishes an `Event` through the EventBus, which:

1. **Persists** it to the unified `events` table
2. **Fans out** to module subscribers
3. **Pushes** to live SSE queues per company

Event envelope: `id, project_id, kind, type, actor {role, id, name}, payload, reason, created_at`.

- `kind: "system" | "conversation"` — one storage model, two renderings. Conversation messages ARE events. (Resolves the v1.0 pending "Timeline data model" question.)
- `reason` makes every agent action explainable (Rule 2).
- Payload shapes are validated per-type via `PAYLOAD_MODELS` in `build_event()`.
- TypeScript types are **generated** from the Pydantic contracts (`scripts/generate_ts_schemas.py` → `packages/event-schemas/ts/`). Frontend never redeclares event shapes.

---

## Modules (as built)

| Module | Responsibility | Status |
|---|---|---|
| `event_bus` | Persist → fan out → SSE push. Dependency floor: depends only on core. | ✅ In-process |
| `projects` | Company CRUD. Founding a company auto-creates a Department with 3 Employees (PM / Engineer / Reviewer personas). | ✅ |
| `tasks` | Mission CRUD, assignment, Meeting messages. Assignment triggers the workflow. | ✅ |
| `workflow_engine` | The brain. PM → Engineer → Reviewer pipeline as background asyncio tasks; publishes every beat; creates CEO Decisions. | ✅ Single fixed pipeline |
| `agent_runtime` | Employee state + validated transitions (state machine in `core/lifecycle`). | ✅ DB-backed |
| `provider_gateway` | Sole path to AI. `MockProvider` (default, zero-key) + `AnthropicProvider` (httpx). Verdicts parsed from a trailing `**Verdict:**` line — provider-agnostic. | ✅ |
| `model_registry` | Logical refs (`planner-default` etc.) → (provider, model). `COMMANDER_PROVIDER=mock\|anthropic`. Changing models never requires code changes. | ✅ Static map |
| `approvals` | CEO Decisions: approve → completed · request_changes → Engineer re-run (attempt+1) · reject → cancelled. | ✅ |
| `timeline` | Cursor-paginated event reads + kind filter. | ✅ |
| `realtime` | SSE stream per company. | ✅ |
| `core/secrets` | `SecretsProvider` port. `DBSecretsProvider`: `settings_kv` override → `.env` fallback, so keys can be pasted in Company Settings at runtime. Write-only through the API. | ✅ Plaintext (local MVP) |
| `auth` | Single hardcoded local CEO. | 🔲 Placeholder |
| `workspace_manager` | Git repo / branch / diff / human-readable summaries. Interface defined only. | 🔲 Interface only |
| `reports` | Daily reports. | 🔲 Placeholder |

### Lifecycles

Agent: `Idle → Assigned → Planning → Working → WaitingReview → (Blocked) → Completed/Failed → Idle`
Task: `backlog → in_progress → waiting_review → completed / cancelled / failed`

All transitions validated in `core/lifecycle/state_machine.py`; every transition emits an event with a reason.

### Dependency Rules

```
Events (core)  →  Domain Modules  →  Workflow  →  API
```

No circular deps. Modules communicate only via EventBus. Agents never call each other or providers directly.

---

## Frontend (Headquarters)

Next.js App Router · TypeScript · Tailwind · TanStack Query. Dark Render.com-style theme, Commander terminology throughout.

- **Headquarters** `/company/[id]` — pending CEO Decisions (hero), company vitals, live Timeline
- **Missions** — kanban (Backlog / In Progress / Waiting CEO Decision / Done) + create modal
- **Mission detail / Meeting** — conversation-kind transcript, CEO can message
- **Employees** — live state cards
- **Company Settings** — provider select, write-only API key field
- Realtime: one SSE connection per company (`RealtimeProvider`), events dedup by id, query invalidation per event

---

## Accepted MVP Tradeoffs (deliberate — see docs/DECISIONS.md)

- In-process EventBus → single API worker only; subscribers run inline in `publish` (a slow subscriber delays publish)
- Secrets stored plaintext in local SQLite
- Conversation filtering for Meetings done in Python (small per-company volume)
- Failure handling minimal: provider error → Mission `failed` + event (full retry/escalation policy in `docs/backend/workflow/FAILURE_HANDLING.md` deferred)
- `create_all` on startup, no migrations

Future extraction points if scaled: Agent Runtime Service, Workflow Service, Event Service (broker-backed bus), Cloud Runner.

---

## Not Built Yet (requires an explicit sprint brief)

Execution sandbox · real code execution · Workspace Manager implementation · deployment/Launch · auth · cloud runner · additional providers (OpenAI/Google/OpenRouter/local) · reports · plugin marketplace · multi-company orgs.

**Sandbox gate:** no AI-generated code is ever executed until an isolation layer exists. Until then, Engineers produce plans/text/diff artifacts only.

---

## Design Principles

1. CEO first, never developer first
2. AI are Employees, never tools
3. Everything observable — nothing happens silently
4. Every important decision explainable
5. Every model replaceable
6. Event-driven, never tightly coupled
7. Mock mode must always work — the product demos with zero API keys

---

## Doc Sync Rule

Any architecture change must update **ARCHITECTURE.md and CLAUDE.md in the same commit**. Desync is an architecture violation.