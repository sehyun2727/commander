# Commander Architecture

Version: v3.0 (V1.1 Target + V1 As-Built)
Status: V1 shipped and tagged `v1.0.0` (Sprint 8). V1.1 in development — this document defines the target architecture V1.1 builds toward.
Supersedes: v2.7 (As-Built, Sprint 8)

**How to read this document.** §1–§5 define the **V1.1 target architecture** — the shape the system is being built into. §6 documents **what exists today (V1 as-built)**, honestly, including where it falls short of the target. §7–§9 are cross-cutting concerns that apply to both. Never confuse the two: if a section says *[V1.1 — not built]*, it requires an explicit sprint brief.

---

## 0. Vision

> **Commander is not a program that gives work to AI. Commander is an operating system for running an AI company.**

A solo operator becomes the CEO of an AI software company. The CEO never manages prompts; the CEO manages an organization.

Every action performed by AI must be **visible, explainable, reviewable, and replaceable.**

The competitive claim is the **organization layer**, not the worker. Workers (agent implementations, models, harnesses) are deliberately replaceable. What Commander owns is the company around them: planning, delegation, review, approval, memory, and accountability.

---

## 1. Organization Model

### 1.1 Two axes, not one chart

Rendering the org as a single tree produces a contradiction, because leadership relates two different ways depending on the phase of work.

**Decision axis — planning.** PM and CTO are peers. Neither reports to the other.

```
                 CEO
                  │
             one channel
                  │
         PM ←── 협의 ──→ CTO
      business         technical
                  │
        Project Specification
                  │
             CEO approval
        Approve / Request change / Reject
```

**Delegation axis — execution.** After approval, work descends and results climb.

```
     PM ──assigns──▶ CTO ──assigns──▶ Employees
                                          │
                                      Reviewer
                                          │
                                    PM judgment
                        Minor → PM · Major → PM+CTO · Critical → CEO
```

The PM is the organization's representative to the CEO in both phases.

### 1.2 Role vs Employee  *[V1.1 — not built]*

This separation is the largest structural change in V1.1.

```
Template
  └── Role (immutable definition)
        ├── role_key, title, category (leadership | worker)
        ├── prompt contract          (immutable output contract, e.g. trailing Verdict)
        ├── tool grants              (whitelist — see Rule #12)
        ├── permissions              (what organizational actions this role may take)
        ├── workflow position        (which pipeline stages it occupies)
        ├── harness                  (execution strategy: one-shot | tool-loop)
        └── default behavior         (founding AgentProfile defaults)

Company
  └── Employee (instance)
        ├── role_key ────────────────▶ Role
        ├── name
        ├── model_ref                (per-employee model)
        └── AgentProfile             (personality / working style / decision style / custom instructions)
```

Constraints:

- **Leadership roles are singletons.** Exactly one PM, one CTO, one Reviewer per company. Enforced at the data layer, not by convention. Never zero, never two.
- **Worker roles are unbounded.** One role may hold many Employees, each on a different model. The PM assigns a Mission to a specific Employee, not to a role.
- **Roles are data (Rule #16).** No engine branch, prompt, or component may test a hardcoded role name. Adding Designer / QA / DevOps / Security / ML Engineer / Data Analyst / Technical Writer must be a template-data change, never an engine change.
- **Employee creation:** Add Employee → select Role → select AI model → select skill template → create. The Role supplies behavior; the Employee supplies identity and model.

Employee count caps may exist as a commercial policy later. The architecture assumes none.

### 1.3 Company Templates  *[architecture in V1.1 — only one template ships]*

A Template is a data document, not code:

```
Template
├── identity        name, description, icon
├── roles[]         the Role definitions above
├── workflow        ordered stage sequence (role_key + stage kind + flags)
├── approval_flow   which decisions are Critical (require CEO) by default
├── tool_registry   the complete set of tools this template may grant to its roles
├── prompt_templates  role contracts and stage prompts
├── deliverable     type key (code | document | …) → selects the renderer
├── vocabulary      status-word overrides
└── starters        suggested first Missions for onboarding
```

Future templates (Marketing Agency, Game Studio, Research Lab, Law Firm, Consulting) must require **adding a data file, not redesigning a system.** That is the whole point of the abstraction.

**Only `software_company` ships in V1.1.** No template picker, no "coming soon" entries — hidden means absent (UX_SPEC §10.2). The gating criterion for a second template is unchanged and still binding: outputs must be **semi-objectively auditable**, or the Decision loop degrades into theater. See §9.2.

---

## 2. High-Level Architecture (V1.1 target)

```text
                              Commander

              ┌───────────────────────────────────────────┐
              │              CEO Workspace                 │
              │   Next.js App Router · TanStack Query      │
              │                                            │
              │   ┌──────────────────┬──────────────────┐  │
              │   │  PM Conversation │  Widget Dock     │  │
              │   │    (primary)     │  (customizable)  │  │
              │   └──────────────────┴──────────────────┘  │
              └────────┬────────────────────▲──────────────┘
                       │                    │
                  REST API              SSE stream
                       │                    │
                       ▼                    │
              ┌────────────────────────────┴──────┐
              │      Commander API Server          │
              │            (FastAPI)               │
              │   auth guard on every route        │
              └──────────────┬─────────────────────┘
                             │
   ┌──────────┬──────────────┼──────────────┬───────────────┐
   ▼          ▼              ▼              ▼               ▼
Workflow   Agent          Event Bus     Provider        Project
 Engine    Runtime       (persist +     Gateway         Memory
   │      (Role/Employee   fan-out +       │          (projection
   │       registry)       SSE push)       ▼           over events)
   │          │                │      Model Registry        │
   │          │                ▼            │               │
   │          │           PostgreSQL   ┌────┴─────┐          │
   │          │          (Alembic-     ▼          ▼          │
   │          │           owned)     Mock     Anthropic      │
   │          │                              (httpx)         │
   │          └──────────── events ──────────────────────────┘
   │
   └── Agent Harness ──▶ SandboxRunner ──▶ Docker (no network, capped, non-root)
        (tool loop,        run_checks only — template-defined commands
         budget-capped)
```

Realtime is **SSE**: one endpoint per company, replays the last 50 events on connect, heartbeat every 15s, client dedups by `event.id`.

`GET /api/health` (liveness, zero dependencies) and `GET /api/health/db` (readiness, real round-trip, `503` on failure) sit outside the auth guard for deploy tooling and the dashboard's own API-down banner.

---

## 3. Core Principle: Everything Is an Event

Every significant company action publishes an `Event` through the EventBus, which **persists** it to the unified `events` table, **fans out** to module subscribers, and **pushes** to live SSE queues per company.

Event envelope: `id, project_id, kind, type, actor {role, id, name}, payload, reason, created_at`.

- `kind: "system" | "conversation"` — one storage model, two renderings. Conversation messages ARE events.
- `reason` makes every agent action explainable (Rule #3).
- Payload shapes are validated per-type via `PAYLOAD_MODELS` in `build_event()`.
- TypeScript types are **generated** from the Pydantic contracts (`scripts/generate_ts_schemas.py`). The frontend never redeclares event shapes.

This single stream is also what makes Project Memory possible without a second source of truth (Rule #14).

### Event families

| Family | Examples | Since |
|---|---|---|
| Mission lifecycle | `task.created`, `task.assigned`, `task.completed`, `task.failed` | V1 |
| Conversation | agent replies, CEO messages, Employee intros | V1 |
| Code | `workspace.initialized`, `code.changed`, `branch.merged` | V1 |
| Execution | `execution.completed` (per-check results) | V1 |
| Decision | decision created / approved / changes requested / rejected | V1 |
| Reliability | `task.recovered`, `budget.exceeded` | *V1.1 S9* |
| Organization | `employee.hired`, `employee.updated`, `role.assigned` | *V1.1 S10–11* |
| Planning | `discussion.turn`, `specification.drafted`, `specification.approved`, `requirement.asked` | *V1.1 S12* |
| Harness | `tool.called`, `checks.reacted`, `self_correction.attempted` | *V1.1 S16–17* |
| Memory | `memory.recorded`, `memory.recalled` | *V1.1 S18* |

---

## 4. Workflow Engine (V1.1 target)

### 4.1 Template-driven stage sequence

The engine must not know the names PM, Engineer, or Reviewer. It executes a sequence the template supplies:

```
StageSpec
  role_key      which role performs this stage
  kind          plan | discuss | produce | review
  lands_code    whether this stage's output is parsed into files and committed
  runs_checks   whether the sandbox runs after this stage
```

The V1 pipeline (`plan → produce → review`) becomes one instance of a general sequence, not the shape. Resume-after-decision addresses a **stage index**, not a role name, because the same role may appear more than once.

### 4.2 Planning phase  *[V1.1 — Sprint 12]*

```
CEO instruction (vague is fine)
   │
   ├─▶ PM drafts business framing
   │
   ├─▶ PM ⇄ CTO discussion loop  (bounded turns, budget-capped per Rule #13)
   │
   ├─▶ missing information? ──▶ PM asks the CEO (Requirement Discovery)
   │                             never invents an answer
   │
   └─▶ Project Specification
         Goal · Target User · Core Features · Technical Constraints
         · Acceptance Criteria · Open Questions · Risks
              │
              ▼
        CEO Decision (Critical) — engineering does not start before approval
```

Requirement Discovery is a first-class behavior: when the specification cannot be completed honestly, the organization asks rather than guesses.

### 4.3 Decision authority  *[V1.1 — Sprint 13]*

| Level | Decided by | Examples |
|---|---|---|
| Minor | PM alone | naming, file placement, small reviewer nits, task ordering |
| Major | PM + CTO | library choice, data model change, API contract change, perf/security tradeoffs |
| Critical | CEO approval | specification approval, scope change, budget overrun, architecture change, external service adoption, irreversible actions |

The goal is fewer CEO interruptions, not fewer CEO rights. Misclassifying a Critical decision as Minor is a trust violation, not an optimization — the classification criteria live in the PM's role contract and are auditable in the Timeline.

### 4.4 Agent Harness  *[V1.1 — Sprints 16–17]*

Worker roles whose harness is `tool-loop` execute as:

```
analyze repo → plan → modify → run_checks → react to results → commit → summarize
```

- **Repository awareness:** read files, search code, understand structure, modify only what is necessary. Never blindly overwrite.
- **Budget (Rule #13):** max tool calls, max tokens, max wall time, max cost. Exhaustion → `blocked` + reason + CEO informed.
- **Every tool call emits an event.** A loop the CEO cannot watch is not acceptable.
- **`run_checks` is the only execution tool that exists** (Rule #12). The harness cannot gain a shell by any path.
- The harness is an implementation of a stable worker interface, so an alternative worker (e.g. an external coding agent) can be substituted without changing events, payroll, or the surrounding organization.

### 4.5 Self-correction  *[V1.1 — Sprint 17]*

A failed check no longer waits for the CEO. The Employee reacts inside its budget; if it still fails, the Reviewer's feedback routes through PM judgment (§4.3) and only reaches the CEO when Critical.

---

## 5. Project Memory  *[V1.1 — Sprint 18]*

Memory is a **projection over the event stream** (Rule #14), not a new datastore.

Recorded categories: architecture decisions · CEO approvals · PM specifications · Reviewer feedback · coding conventions · failed attempts · successful solutions · prior discussions.

Two behaviors depend on it:

- **Continuity** — Mission N starts by recalling what Missions 1..N-1 established, instead of re-deriving it.
- **Sprint Learning** — when work fails, the next attempt reads the previous attempts, the Reviewer's comments, and the failure reasons *first*. This is project learning, not model fine-tuning.

Selective recall is mandatory: injecting the entire history into every prompt would blow the context window. Relevance selection is itself a design surface and must be observable (`memory.recalled` events).

---

## 6. V1 As-Built (what exists today)

### 6.1 Modules

| Module | Responsibility | Status |
|---|---|---|
| `event_bus` | Persist → fan out → SSE push. Depends only on core. | ✅ In-process |
| `projects` | Company CRUD. Founding auto-creates a Department with 3 Employees (PM / Engineer / Reviewer) from the template, posts each intro as a conversation event, serves starter Missions. | ✅ |
| `tasks` | Mission CRUD, assignment, Meeting messages, `deliverable_type: "code" \| "document"`. Assignment triggers the workflow. Serves `GET /tasks/{id}/diff`. | ✅ |
| `workflow_engine` | The brain. PM → Engineer → checks → Reviewer as background asyncio tasks. Parses FILE blocks, commits to the mission branch, runs matched `CheckSpec`s through `SandboxRunner`, hands the Reviewer a Change Summary + real diff + checks summary. Approve → merge; reject → branch preserved; request_changes → same-branch recommit; merge conflict → `blocked` with a plain-language reason. | ⚠️ **Single fixed 3-stage pipeline, positional role unpacking** — Sprint 9 generalizes |
| `agent_runtime` | Employee state + validated transitions. Founds Employees with role-keyed defaults. | ⚠️ **Agent ≡ role; no Role/Employee split** — Sprints 10–11 |
| `templates` | Static internal data file (`app/templates/software_company.py`). Single source of the founding trio, pipeline order, role contracts, founding profile defaults, onboarding data, `CheckSpec`s. | ⚠️ **Covers roles+workflow only; no tool registry, approval flow, or template registry** — Sprints 10–11, 19 |
| `agent_profiles` | CEO-editable personality / working style / decision style / custom instructions / per-Employee model override, persisted as JSON on `AgentORM.profile`. | ✅ |
| `prompt_builder` | Pure function: profile + role → system prompt. Role contract appended **last**, so no custom instruction can suppress the Reviewer's trailing `**Verdict:**`. | ✅ |
| `provider_gateway` | Sole path to AI. `MockProvider` (default, zero-key) + `AnthropicProvider` (streaming, retry-with-backoff). Three-tier model resolution: Employee override > CEO per-role override > registry default. | ✅ |
| `model_registry` | Logical refs (`planner-default`, `builder-default`, …) → (provider, model). | ✅ |
| `costs` | Per-call token usage → USD. Payroll (monthly, per company + per Employee) and Mission Budget (all-time, per mission). | ⚠️ **Accounting only; no enforcement** — Sprint 9 adds budget guards |
| `approvals` | CEO Decisions: approve → completed · request_changes → re-run (attempt+1) · reject → cancelled. | ✅ |
| `timeline` | Cursor-paginated event reads + kind filter, newest-first. | ✅ |
| `realtime` | SSE stream per company; live streaming deltas for in-flight replies. | ✅ |
| `reports` | On-demand CEO Daily Report from the Timeline's own history. | ✅ |
| `situation` | `GET /projects/{id}/situation` — 1–2 sentence PM-voiced glanceable status, generated with a deterministic mock fallback. | ⚠️ **Repurposed in V1.1** as the PM conversation's opening report (UX_SPEC §3.2); the standalone UI block is removed |
| `core/secrets` | `SecretsProvider` port; `DBSecretsProvider` reads `settings_kv` override → `.env` fallback. Write-only through the API. | ✅ Plaintext (local MVP) |
| `workspace_manager` | One real git repo per company; branch-per-mission; path validation (relative-only, no `..`, no symlink escape, no `.git`); 30 files / 256KB / text-only per write; truncating `diff()`. Read-only browsing routes. | ✅ |
| `sandbox` | The one controlled place AI-generated code is executed. `SandboxRunner` port + `DockerSandbox` + `FakeSandbox`. See §7. | ✅ |
| `core/db` + Alembic | Postgres default (Docker Compose), SQLite for tests. Schema owned by Alembic. | ✅ |
| `core/boot_checks` | Fail-fast startup validation before `init_db()`. | ✅ |
| `auth` | — | 🔲 **Empty placeholder** — Sprint 9 |
| `roles`, `employees`, `specifications`, `memory`, `widgets` | — | 🔲 **Do not exist** — Sprints 10–18 |

### 6.2 Lifecycles

Agent: `Idle → Assigned → Planning → Working → WaitingReview → (Blocked) → Completed/Failed → Idle`
Task: `backlog → in_progress → waiting_review → completed / cancelled / failed`

All transitions validated in `core/lifecycle/state_machine.py`; every transition emits an event with a reason.

### 6.3 Dependency rules

```
Events (core)  →  Domain Modules  →  Workflow  →  API
```

No circular deps. Modules communicate only via EventBus. Agents never call each other or providers directly.

### 6.4 Known structural debt entering V1.1

Identified by code review at the V1.1 planning gate; scheduled into Sprint 9:

1. **Orphaned missions.** The pipeline runs as fire-and-forget `asyncio.create_task` with no recovery on startup. A restart leaves missions permanently `in_progress`, and no cancel route exists.
2. **No budget enforcement.** `costs` records spend after the fact; nothing stops a runaway or concurrent burn.
3. **Detached ORM reuse.** `_run_pipeline` reads ORM attributes after its session closes; a fallback currently masks it. Loops will break it.
4. **Positional role unpacking.** `_PM, _ENGINEER, _REVIEWER = TEMPLATE.roles` breaks the moment a fourth role exists.
5. **Sandbox hardening gaps.** `--cap-drop ALL` and `--security-opt no-new-privileges` are not set (residual, low severity — non-root and no-network already hold).

---

## 7. Security Model

### 7.1 Execution — what runs, and what never does

- **The command is never AI output.** `CheckSpec.command` (e.g. `pytest`, `node --test`) is trusted data in the template. The Employee's output — deliverable, FILE blocks, prose — is never parsed for commands and never reaches a shell. Only the *presence* of matching files (`detect_globs`) selects which fixed commands run.
- **Isolation, per run:** fresh container → tar-copy the landed branch files in → run one fixed command → capture output tail → destroy unconditionally, even on failure or timeout. No container is reused.
- **Constraints:** no network (`--network none`), memory / CPU / PIDs caps, non-root user, 120s hard kill-and-reap. *Sprint 9 adds `--cap-drop ALL` and `--security-opt no-new-privileges`.*
- **Fails closed, never open:** Docker missing, image absent, check timed out, or CEO toggle off → no-op (`check_results: null`, zero events). It never falls back to running anything unsandboxed. Capability is probed live, never assumed.
- **The harness changes none of this.** When agents gain tool loops (Sprint 16), the only execution tool is `run_checks`. There is no path by which an agent obtains a shell, and blocklists are never accepted as a substitute for the whitelist (Rule #12).

### 7.2 Authorization  *[V1.1 — Sprint 9]*

- Session-cookie authentication (HttpOnly), session tokens stored as hashes, sliding expiry.
- Every Company has an owner; every route outside health and auth requires a session.
- Cross-account access returns **404, not 403** — existence is not disclosed (Rule #15).
- Password hashes only; no plaintext column exists anywhere in the schema.
- The identity provider is an interface with one implementation (local email+password); adding Google OAuth must be one new file, not a refactor.

---

## 8. Frontend Architecture

Next.js App Router · TypeScript · Tailwind · TanStack Query. Dark, Render-inspired calm.

**V1.1 target layout** (detailed in UX_SPEC §3–§4): entering a company presents **the PM conversation as the primary surface**, with a customizable **Widget Dock** beside it and a thin sidebar for deeper pages. New CEO-facing capability lands as a Widget or a Sidebar page (Rule #17) — never bolted onto the conversation.

**V1 as-built surfaces** (all real, all shipping today): My Companies · Headquarters · Missions kanban + detail · Employees + profile · Timeline (CEO/Technical toggle, filters, digest grouping) · Decisions (Pending/History) · Reports · Workspace browser · Company Settings. Most of these are not discarded in V1.1 — they become Sidebar pages, and their summaries become Widgets. **Headquarters is the one exception: it is absorbed into the CEO Workspace rather than surviving as its own page.** Same route (`/company/[id]`), same purpose, different shape — a conversation-plus-widget-dock replaces a standalone dashboard. Its four blocks map as:

| V1 Headquarters block | V1.1 destination |
|---|---|
| Decision strip (hero) | Pending Approvals widget + the "needs your decision" section of the PM Report |
| Situation Report | PM Report (UX_SPEC §3.2) |
| Vitals (4 tiles) | Progress · Employees · Risks · Costs widgets |
| Timeline excerpt | Timeline widget |

Rationale: the widget dock already replicates everything Headquarters does; keeping both would be a direct duplication and would force the CEO to guess which screen to check.

Cross-cutting: one SSE connection per company, events dedup by id and invalidate queries; generated event types only; `ApiStatusBanner` polls health; SSE connection status surfaces as a "Reconnecting…" pill; a persistent "Simulation mode" badge whenever the company runs on mock.

---

## 9. Accepted Tradeoffs & Deferred Risks

### 9.1 Accepted MVP tradeoffs (deliberate — see `docs/DECISIONS.md`)

- In-process EventBus → single API worker; subscribers run inline in `publish`
- Secrets stored plaintext in the database
- Conversation filtering done in Python (small per-company volume)
- Minimal failure handling: provider error → Mission `failed` + event
- No connection pooling tuning, read replicas, or backup tooling — single local Postgres assumed
- `/api/health/db` is a synchronous round-trip, not a polled cache

Future extraction points if scaled: Agent Runtime Service, Workflow Service, broker-backed Event Service, Cloud Runner (the local `DockerSandbox` is the first materialization of that port).

### 9.2 Why only one template ships in V1.1

The architecture is template-driven from Sprint 10. Shipping a second template is a separate, later decision governed by these risks, which are unchanged from the V1 analysis:

1. **The verifiability cliff.** Software is the easiest domain in which to build trust: tests pass or fail, diffs can be audited. Marketing copy and research have no such ground truth, and a Reviewer's verdict becomes an opinion. Every new template needs real domain audit criteria or the Decision loop — the product's core — degrades into theater.
2. **The prompt-pack trap.** A template that only swaps titles and personas produces N orgs with identical shallow output. Real differentiation needs deliverable types, audit criteria, and workflow shapes per domain.
3. **Wedge dilution.** "AI dev company" is a sharp story; "OS for any AI organization" is a vision statement. Marketing the vision before the wedge wins means competing everywhere and excelling nowhere.
4. **Surface explosion.** Every template multiplies the testing matrix, mock content, onboarding paths, and support burden.

Criterion for template #2: the software company sustains real usage quality first, and the second domain is chosen for auditability (e.g. a technical-documentation studio) before opinion-heavy domains.

---

## 10. Doc Sync Rule

Any architecture change must update **ARCHITECTURE.md and CLAUDE.md in the same commit**, and UX_SPEC.md too when the change is CEO-facing. Desync is an architecture violation.

These three documents must never contradict each other. When they do, `ARCHITECTURE.md` governs system structure, `UX_SPEC.md` governs the CEO's experience, and `CLAUDE.md` governs day-to-day implementation rules — reconcile in that order of scope and fix all three in one commit.
