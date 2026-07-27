# Commander Architecture

Version: v2.7 (As-Built)
Status: Synced with Sprint 8 ("V1 Release") implementation — V1 tagged `v1.0.0` — 2026-07
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
      │          │         PostgreSQL   ┌────┴─────┐
      │          │        (default,     ▼          ▼
      │          │        via Docker;  Mock     Anthropic
      │          │        SQLite for   Provider   Provider
      │          │        tests only) (default)  (httpx)
      │          │        events, projects,
      │          │        tasks, agents,
      │          │        approvals, settings_kv,
      │          │        cost_entries, reports —
      │          │        schema owned by Alembic
```

Realtime is **SSE** (not WebSocket): one endpoint per company, replays last 50 events on connect, heartbeat every 15s, client dedups by `event.id`.

`GET /api/health` (liveness, zero dependencies) and `GET /api/health/db` (readiness, real DB round-trip, `503` on failure) sit beside the API server for deploy tooling and the dashboard's own API-down banner to poll.

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
| `workflow_engine` | The brain. PM → Engineer → checks → Reviewer pipeline as background asyncio tasks; publishes every beat; creates CEO Decisions. System prompts built per call via `prompt_builder.build(profile, role, deliverable_type)`. For code missions, the Engineer's FILE-block output is parsed (`parsing.parse_file_blocks` / `parse_change_summary`), written + committed to the mission branch via `WorkspaceManager`, then `_run_checks` detects which of the template's `CheckSpec`s apply to the landed file tree and runs them through `SandboxRunner` before the Reviewer sees the diff — the Reviewer's context becomes the Change Summary + a real (possibly truncated) diff + a short plain-language checks summary, never the raw deliverable text. Zero valid FILE blocks silently falls back to a document mission rather than failing the pipeline; execution disabled, no sandbox, or zero matched checks all short-circuit `_run_checks` to a no-op with zero events. Approve → merge → `branch.merged`; reject → branch left unmerged; request_changes → same-branch recommit (attempt+1); merge conflict → `blocked` with a plain-language reason (no AI code is ever executed to resolve it). | ✅ Single fixed pipeline |
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
| `sandbox` | The one controlled place AI-generated code is ever executed. `SandboxRunner` port (`core/interfaces/sandbox.py`) + `DockerSandbox` (`docker create` → tar-copy the landed branch files in → run a template-defined `CheckSpec` command → capture stdout/stderr tail (10k chars) → always destroy the container) and `FakeSandbox` for tests. Constraints: no network, memory/cpu/pids caps, non-root, 120s hard kill, auto-remove. `CheckSpec`s (name / `detect_globs` / command) are trusted data from `templates/software_company.py` — never AI-authored or AI-chosen; `detection.py` glob-matches the landed file tree to decide which checks apply. `GET /api/system/capabilities` probes Docker + the sandbox image at runtime; `execution-settings` (`settings_kv`, default enabled) lets the CEO turn checks off per company. Degrades silently to a no-op (zero events, `check_results: null`) when Docker/the image is absent or the toggle is off — the rest of the pipeline is unaffected either way. | ✅ Docker (graceful no-op without Docker Desktop) |
| `core/db` + Alembic | PostgreSQL (via `docker-compose`, Phase 1) is the default datastore; SQLite (`aiosqlite`) remains a zero-dependency fallback for tests and CI. Schema is owned by Alembic (`apps/api/alembic/`, async env) — `create_all` now only fires for the SQLite test path; a Postgres boot runs `alembic upgrade head` instead (`db.py: init_db`). `make db-up` / `db-upgrade` / `db-downgrade` wrap the compose lifecycle + migrations. | ✅ |
| `core/boot_checks` | Fail-fast startup validation, run before `init_db()` in `main.py`'s lifespan: `COMMANDER_PROVIDER=anthropic` with no key anywhere, or a `DATABASE_URL` that isn't `sqlite`/`postgresql`, raises `BootConfigError` and exits cleanly (`SystemExit(1)`, plain-language stderr message, no traceback) instead of failing confusingly on the first Mission or with a raw connection error. | ✅ |

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
- **Mission detail / Meeting** — conversation-kind transcript with live streaming replies, CEO can message, Mission Budget spent, reuses `DecisionCard` for its pending Approval. Code missions render `ChangeSummaryCard` instead of raw deliverable text: Change Summary + aggregate stats (`N files +A -D`) + verdict chip, with the real diff lazily fetched and expandable per-file only on request — the diff is never the landing view. When a mission ran automated checks, `ExecutionResults` (chips per check + duration, output tail behind a click) appears below the deliverable, and both `ChangeSummaryCard` and `DecisionCard` show a one-line checks verdict (`checksSummary()`, computed client-side from `check_results` so it can never drift from the chip data)
- **Workspace** `/company/[id]/workspace` — the company's real git-backed codebase: file tree + file viewer (`GET /projects/{id}/workspace/tree`\|`/file`) and recent merge history (`GET /projects/{id}/workspace/merges`), all read-only
- **Employees** — live state cards
- **Decisions** `/company/[id]/decisions` — Pending / History tabs; `DecisionCard`'s full anatomy (Problem / Recommendation with reviewer attribution / Risk / Impact + Approve · Request changes · Reject), History adds the CEO's decision + outcome
- **Timeline** `/company/[id]/timeline` — full-page live feed (cursor-paginated "load earlier"), filter tabs (All / Meetings / Decisions / System), CEO view ↔ Technical view toggle (hidden mechanism-event set defined as data in `lib/timelineVocabulary.ts`), 4+ consecutive minor system events collapse into an expandable digest row. `execution.completed` is never digested — in CEO view its server-set `reason` already reads as a plain verdict via the default row; Technical view gets a dedicated expandable `ExecutionRow` with a per-check breakdown
- **Reports** `/company/[id]/reports` — list + Generate Report button; **Report detail** `/company/[id]/reports/[reportId]` — full report + past-report history
- **Company Settings** — provider select, write-only API key field, per-role model reassignment, Execution Sandbox toggle (always interactive — a durable preference, not a live control — with an explanatory note when Docker Desktop/the sandbox image is unavailable)
- **Status vocabulary** — one external-facing status word table (`components/StatusWord.tsx`) shared by every card/badge/kanban column/filter; `companyStatusWord()` reduces a company's Missions to a single priority-ranked token for `CompanyCard`
- Realtime: one SSE connection per company (`RealtimeProvider`), events dedup by id, query invalidation per event, transient streaming-delta bubble for in-flight replies
- **Resilience (Sprint 7)** — `ApiStatusBanner` polls `GET /api/health` every 5s (`retry: false`) and shows a sticky top banner when the API is unreachable; `useEventStream` surfaces a `ConnectionStatus` ("connecting" \| "open" \| "reconnecting") through `RealtimeProvider`/`useRealtimeConnectionStatus`, rendered as a small "Reconnecting…" pill in the Sidebar. The browser's native `EventSource` already retries indefinitely on its own — this only adds visibility, not retry logic.

---

## Accepted MVP Tradeoffs (deliberate — see docs/DECISIONS.md)

- In-process EventBus → single API worker only; subscribers run inline in `publish` (a slow subscriber delays publish)
- Secrets stored plaintext (in Postgres/SQLite, whichever backs the deployment)
- Conversation filtering for Meetings done in Python (small per-company volume)
- Failure handling minimal: provider error → Mission `failed` + event (full retry/escalation policy in `docs/backend/workflow/FAILURE_HANDLING.md` deferred)
- No connection pooling tuning, no read replicas, no backup/restore tooling — a single Postgres container is assumed local-dev scale
- `/api/health/db` is a synchronous round-trip check, not a background-polled health cache — fine at V1's request volume, would need revisiting under real load

Future extraction points if scaled: Agent Runtime Service, Workflow Service, Event Service (broker-backed bus), Cloud Runner (Sprint 6's local `DockerSandbox` is the first materialization of this — same `SandboxRunner` port a hosted/remote runner would implement).

---

## Not Built Yet (requires an explicit sprint brief)

Deployment/Launch · auth · hosted/remote cloud runner (beyond the local Docker sandbox) · additional providers (OpenAI/Google/OpenRouter/local) · plugin marketplace · multi-company orgs.

**Sandbox gate:** AI-generated code is never executed, installed, evaluated, or spawned on the host, and never via an AI-chosen command — full stop. Sprint 6 opens exactly one controlled exception to "nothing is ever run": template-defined, trusted `CheckSpec` commands (never Engineer/AI-authored) executed inside an isolated, network-disconnected, resource-capped, non-root, auto-destroyed Docker container, gated behind a live capability probe and a CEO-controlled per-company toggle, and silently absent when Docker isn't available. The Reviewer still audits the diff statically; sandboxed check output is additional evidence handed to the Reviewer and the CEO, not a replacement for that audit.

---

## Security Model: Sandboxed Execution (Sprint 6)

What actually runs, and what never does:

- **The command is never AI output.** `CheckSpec.command` (e.g. `pytest`, `node --test`) is trusted data hardcoded in `templates/software_company.py`. The Engineer's own output — the deliverable, the FILE blocks, any prose — is never parsed for commands and never reaches a shell. Only the *presence* of matching files (via `detect_globs`) decides which trusted, fixed commands run.
- **Isolation, per run:** `docker create` a fresh container from the pinned sandbox image → tar-copy the landed branch's files in → run the one fixed command → capture stdout/stderr (10k-char tail) and exit code → `docker rm` unconditionally, even on failure/timeout. No container is ever reused across checks or missions.
- **Constraints on the container:** no network (`--network none`), memory/CPU/PIDs caps, non-root user, 120s hard kill-and-reap. A stuck or malicious process can't outlive the timeout, can't exhaust the host, and can't reach anything else on the network.
- **Fails closed, never open:** if Docker isn't running, the sandbox image isn't built, a check times out, or the CEO has the toggle off, `_run_checks` short-circuits to a no-op (`check_results: null`, zero events) — it never falls back to running anything unsandboxed. Capability is probed live (`GET /api/system/capabilities`), never assumed.
- **What the sandbox is not:** it does not make the product "run AI code" in the general sense — it runs a small, fixed menu of static-analysis/test commands the CEO's own template chose in advance, against files the CEO already reviewed were committed. The Reviewer's static diff audit is unchanged and still authoritative; check output is corroborating evidence, never a substitute for it.

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