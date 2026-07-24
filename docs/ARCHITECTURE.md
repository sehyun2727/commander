# Commander Architecture

Version: v2.4 (As-Built)
Status: Synced with Sprint 5 ("Workspace") implementation — 2026-07
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
      │          │         settings_kv,
      │          │         cost_entries,
      │          │         reports)
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
- Code-mission events: `workspace.initialized` (first code mission for a company), `code.changed` (Engineer commit landed on the mission branch — stats payload), `branch.merged` (CEO approval merged the branch into `main`). Rendered by the same generic Timeline row via `event.reason` — no special-cased renderer needed.
- `reason` makes every agent action explainable (Rule 2).
- Payload shapes are validated per-type via `PAYLOAD_MODELS` in `build_event()`.
- TypeScript types are **generated** from the Pydantic contracts (`scripts/generate_ts_schemas.py` → `packages/event-schemas/ts/`). Frontend never redeclares event shapes.

---

## Modules (as built)

| Module | Responsibility | Status |
|---|---|---|
| `event_bus` | Persist → fan out → SSE push. Dependency floor: depends only on core. | ✅ In-process |
| `projects` | Company CRUD. Founding a company auto-creates a Department with 3 Employees (PM / Engineer / Reviewer), each founded with default `AgentProfile` field values, and posts each Employee's template `intro` line as a task-less conversation event. `GET /projects/{id}/starters` serves the template's one-click starter Mission suggestions. | ✅ |
| `tasks` | Mission CRUD, assignment, Meeting messages, `deliverable_type: "code" \| "document"` (defaults `"code"`). Assignment triggers the workflow. Serves `GET /tasks/{id}/diff` (real diff + truncation flag) since it owns `branch_name`. | ✅ |
| `workflow_engine` | The brain. PM → Engineer → Reviewer pipeline as background asyncio tasks; publishes every beat; creates CEO Decisions. System prompts built per call via `prompt_builder.build(profile, role, deliverable_type)`. For code missions, the Engineer's FILE-block output is parsed (`parsing.parse_file_blocks` / `parse_change_summary`), written + committed to the mission branch via `WorkspaceManager`, and the Reviewer's context becomes the Change Summary + a real (possibly truncated) diff — never the raw deliverable text. Zero valid FILE blocks silently falls back to a document mission rather than failing the pipeline. Approve → merge → `branch.merged`; reject → branch left unmerged; request_changes → same-branch recommit (attempt+1); merge conflict → `blocked` with a plain-language reason (no AI code is ever executed to resolve it). | ✅ Single fixed pipeline |
| `agent_runtime` | Employee state + validated transitions (state machine in `core/lifecycle`). Founds Employees with role-keyed default `AgentProfile`s. | ✅ DB-backed |
| `templates` | Not an event-driven module — a static internal data file (`app/templates/software_company.py`, §10.6). Single source of the founding trio, pipeline role order, each role's immutable prompt contract, founding profile defaults, and onboarding data (intro lines, starter Missions). `agent_runtime`, `workflow_engine`, and `prompt_builder` all read from it; no component branches on a hardcoded role name. One template, no picker (§10.4). | ✅ |
| `agent_profiles` | CEO-editable Employee configuration: `AgentProfile` (personality / working style / decision style / custom instructions / per-Employee model override), persisted as JSON on `AgentORM.profile`. `GET`/`PUT /api/agents/{agent_id}/profile`; `PUT` emits `agent.profile_updated` (changed fields only) via EventBus. | ✅ |
| `prompt_builder` | Pure function: `AgentProfile` + role → system prompt. Layers personality/working/decision trait text, then optional custom instructions, then the immutable per-role contract appended LAST — no profile configuration (including adversarial custom instructions) can suppress the Reviewer's trailing `**Verdict:**` requirement. No DB/provider deps. | ✅ |
| `provider_gateway` | Sole path to AI. `MockProvider` (default, zero-key) + `AnthropicProvider` (httpx, streaming, retry-with-backoff). Verdicts parsed from a trailing `**Verdict:**` line — provider-agnostic. Resolves models via three-tier precedence: Employee `profile.model_ref` override > CEO per-role override > registry default. | ✅ |
| `model_registry` | Logical refs (`planner-default`, `builder-default`, `reviewer-default`, `reporter-default`) → (provider, model). `COMMANDER_PROVIDER=mock\|anthropic`. CEO can reassign the model behind planner/builder/reviewer per company (override stored in `settings_kv`, Anthropic only — mock roles are template-locked). | ✅ |
| `costs` | Per-call token usage → USD via `PRICE_PER_MILLION_TOKENS`. Payroll (calendar-month, per company + per Employee) and Mission Budget (all-time, per mission) summaries. | ✅ |
| `approvals` | CEO Decisions: approve → completed · request_changes → Engineer re-run (attempt+1) · reject → cancelled. | ✅ |
| `timeline` | Cursor-paginated event reads + kind filter, newest-first (`cursor=None` returns the most recent page; passing back the returned `next_cursor` walks further into the past). | ✅ |
| `realtime` | SSE stream per company; live streaming deltas for in-flight replies. | ✅ |
| `reports` | On-demand CEO Daily Report: trailing-24h summary (missions, decisions, payroll, highlights) from the Timeline's own event history, written via `ProviderGateway`. Now its own page/list (`/reports`), not a Headquarters card. | ✅ |
| `situation` | `GET /projects/{id}/situation` — 1-2 sentence PM-voiced glanceable status (pending decisions, missions in flight, last notable event), generated via `ProviderGateway` with a deterministic mock fallback. Ephemeral/uncached, regenerated on read; distinct from the Daily Report. | ✅ |
| `core/secrets` | `SecretsProvider` port. `DBSecretsProvider`: `settings_kv` override → `.env` fallback, so keys can be pasted in Company Settings at runtime. Write-only through the API. | ✅ Plaintext (local MVP) |
| `auth` | Single hardcoded local CEO. | 🔲 Placeholder |
| `workspace_manager` | One real git repo per company at `${COMMANDER_WORKSPACE_ROOT}/{project_id}` (`LocalGitWorkspaceManager`, plain `git` CLI via async subprocess). Branch-per-mission (`mission/{task_id[:8]}`); lazy-init with a `README.md` on `main`; path validation (relative-only, no `..`, no symlink escape, no `.git`); limits of 30 files / 256KB / text-only per write (violations skipped + reported, never fail the mission); `diff()` truncates at `max_chars` and flags `truncated`. Read-only browsing (`tree`/`file`/`merges`) served from `workspace_manager/routes.py`; the per-mission diff is served from `tasks/routes.py` since only `TaskORM` knows `branch_name` (DECISIONS.md #94). | ✅ |

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

- **My Companies** `/` — founding invitation (name + optional "what should it build") that skips straight to a live Mission when filled in; `CompanyCard` per company (status word, "n/m Missions" milestone bar, live employee avatar stack, latest activity line, decision badge)
- **Headquarters** `/company/[id]` — top to bottom: Decision strip hero (pending `DecisionCard`s, quiet "Nothing needs your decision." when empty) → Situation Report block (PM attribution + timestamp) → four Vitals linked to their source pages (Missions active, Employees working now, Risks open — proxied via FAILED-mission count, Payroll this month) → condensed live Timeline with an "Open full Timeline" link
- **Missions** — kanban (Backlog / Developing / Needs your decision / Done); empty state offers a one-click starter Mission (from the template's `starters`, via `GET /projects/{id}/starters`) + create modal; create form includes a code/document deliverable toggle (defaults code)
- **Mission detail / Meeting** — conversation-kind transcript with live streaming replies, CEO can message, Mission Budget spent, reuses `DecisionCard` for its pending Approval. Code missions render `ChangeSummaryCard` instead of raw deliverable text: Change Summary + aggregate stats (`N files +A -D`) + verdict chip, with the real diff lazily fetched and expandable per-file only on request — the diff is never the landing view
- **Workspace** `/company/[id]/workspace` — the company's real git-backed codebase: file tree + file viewer (`GET /projects/{id}/workspace/tree`\|`/file`) and recent merge history (`GET /projects/{id}/workspace/merges`), all read-only
- **Employees** — live state cards
- **Decisions** `/company/[id]/decisions` — Pending / History tabs; `DecisionCard`'s full anatomy (Problem / Recommendation with reviewer attribution / Risk / Impact + Approve · Request changes · Reject), History adds the CEO's decision + outcome
- **Timeline** `/company/[id]/timeline` — full-page live feed (cursor-paginated "load earlier"), filter tabs (All / Meetings / Decisions / System), CEO view ↔ Technical view toggle (hidden mechanism-event set defined as data in `lib/timelineVocabulary.ts`), 4+ consecutive minor system events collapse into an expandable digest row
- **Reports** `/company/[id]/reports` — list + Generate Report button; **Report detail** `/company/[id]/reports/[reportId]` — full report + past-report history
- **Company Settings** — provider select, write-only API key field, per-role model reassignment
- **Status vocabulary** — one external-facing status word table (`components/StatusWord.tsx`) shared by every card/badge/kanban column/filter; `companyStatusWord()` reduces a company's Missions to a single priority-ranked token for `CompanyCard`
- Realtime: one SSE connection per company (`RealtimeProvider`), events dedup by id, query invalidation per event, transient streaming-delta bubble for in-flight replies

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

Execution sandbox · real code execution · deployment/Launch · auth · cloud runner · additional providers (OpenAI/Google/OpenRouter/local) · plugin marketplace · multi-company orgs.

**Sandbox gate:** no AI-generated code is ever executed, installed, evaluated, or spawned until an isolation layer exists — this holds even after Sprint 5's real git workspace. Engineers produce real committed files reviewed by diff; nothing is ever run. The Reviewer audits statically only.

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