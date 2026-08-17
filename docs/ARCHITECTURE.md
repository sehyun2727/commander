# Commander Architecture

Version: v3.1 (V1.1 Target + V1 As-Built)
Status: V1 shipped and tagged `v1.0.0` (Sprint 8). V1.1 in development — this document defines the target architecture V1.1 builds toward. Sprint 9 (Foundation & Authentication) landed accounts/auth, pipeline data-ification, and operational reliability (orphan recovery, cancel, budget guard).
Supersedes: v3.0 (Sprint 8)

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

### 1.2 Role vs Employee  *[Sprint 10 ✅ structural split; Sprint 11 ✅ hiring flow]*

This separation is the largest structural change in V1.1.

Sprint 10 shipped: `RoleSpec` as a frozen, template-owned dataclass
(`role_key`, `title`, `category`, `singleton`, `description`, `default_profile`);
`AgentORM.role_key` replacing the old `role` column; singleton enforcement
at the service layer (`SingletonRoleViolation`); idle-first Role → Employee
resolution (`employee_resolution.resolve_employee_for_role`) with an
`AGENT_RESOLVED` event; a read-only Roles API
(`GET /api/projects/{id}/roles`); and the Rule #16 AST guard
(`tests/test_role_hardcoding_guard.py`). `tools`/`permissions` exist on
`RoleSpec` as declared, empty fields (`tools=()`) — no real grants are
wired yet.

Sprint 11 shipped: a first-class `cto` `RoleSpec` (leadership, singleton,
`founding=False` — vacant at company creation, hireable by the CEO rather
than auto-seeded, see `docs/DECISIONS.md` #178); an authoritative hiring
service (`app/modules/agent_runtime/service.py::hire_employee`) that is the
only insertion path for new `AgentORM` rows; a database-backed singleton
lock (`role_singleton_locks`, keyed on `(project_id, role_key)`, one row per
occupied singleton Role) that makes concurrent singleton hiring race-safe at
the transaction level rather than via a check-then-insert in application
code (see §7.2 below and DECISIONS #182); a canonical, typed, server-owned
skill-template registry (`app/modules/skill_templates/`, 3 entries,
presentation-only — no runtime capability grant); a hiring/configuration API
(`POST /api/projects/{id}/agents`, extended `PUT /api/agents/{id}/profile`,
`GET /api/projects/{id}/skill-templates`); and an `AGENT_HIRED` event. Still
pending: any role beyond PM/CTO/Engineer/Reviewer, and PM↔CTO planning
(Sprint 12).

```
Template
  └── Role (immutable definition)
        ├── role_key, title, category (leadership | worker)
        ├── singleton, founding      (occupancy + auto-seed policy)
        ├── prompt contract          (immutable output contract, e.g. trailing Verdict)
        ├── tool grants              (whitelist — see Rule #12)
        ├── permissions              (what organizational actions this role may take)
        ├── workflow position        (which pipeline stages it occupies)
        ├── harness                  (execution strategy: one-shot | tool-loop)
        └── default behavior         (founding AgentProfile defaults)

Company
  └── Employee (instance, created only by hire_employee / founding seed)
        ├── role_key ────────────────▶ Role
        ├── name
        ├── model_ref                (per-employee model; falls back through the
        │                             3-tier RoutedProviderGateway resolution)
        └── AgentProfile             (personality / working style / decision style /
                                       custom instructions / skill_template_key)
```

Constraints:

- **Leadership roles are singletons.** Exactly one PM, one CTO, one Reviewer per company. Enforced at the data layer via `role_singleton_locks`, not by convention or a service-level check-then-insert. Never zero, never two — including under concurrent hiring requests (see §7.2).
- **Worker roles are unbounded.** One role may hold many Employees, each on a different model and skill template. The PM assigns a Mission to a specific Employee, not to a role, via the deterministic resolver (§1.2 resolver note below and `employee_resolution.py`).
- **Roles are data (Rule #16).** No engine branch, prompt, or component may test a hardcoded role name. Adding Designer / QA / DevOps / Security / ML Engineer / Data Analyst / Technical Writer must be a template-data change, never an engine change. The AST guard (`tests/test_role_hardcoding_guard.py`) scans all of `app/` except `app/templates/` and derives its role-key list from the live template, so it automatically covers new Roles and new production modules (skill_templates, agent_runtime) without needing an update.
- **Employee creation:** Hire Employee → select Role → select AI model → select skill template → create. The Role supplies behavior; the Employee supplies identity, model, and skill template. Role, model, and skill-template options are always read from their respective canonical registries (`TEMPLATE.roles`, `model_registry`, `skill_templates.registry.SKILL_TEMPLATES`) — never duplicated as a second list in a route or a frontend component.
- **Employee configuration is independent per Employee.** Changing one Employee's `model_ref` or `skill_template_key` (`PUT /api/agents/{id}/profile`) never mutates `RoleSpec` or any other Employee's configuration, and can never transfer the Employee's `role_key` or company ownership (`ProfileUpdateRequest` has no `role`/`project_id` field and `extra="forbid"`).

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
| Reliability | `task.recovered`, `budget.exceeded` | V1.1 S9 ✅ |
| Organization | `agent.profile_updated` (pre-V1.1), `agent.resolved` (S10 ✅), `agent.hired` (S11 ✅) | V1 / V1.1 S10–11 ✅ |
| Planning | `discussion.turn`, `specification.drafted`, `specification.approved`, `requirement.asked` | *V1.1 S12* |
| Harness | `tool.called`, `checks.reacted`, `self_correction.attempted` | *V1.1 S16–17* |
| Memory | `memory.recorded`, `memory.recalled` | *V1.1 S18* |

---

## 4. Workflow Engine (V1.1 target)

### 4.1 Template-driven stage sequence  *[V1.1 — Sprint 9 ✅]*

The engine must not know the names PM, Engineer, or Reviewer. It executes a sequence the template supplies:

```
StageSpec
  role_key      which role performs this stage
  kind          plan | discuss | produce | review
  lands_code    whether this stage's output is parsed into files and committed
  runs_checks   whether the sandbox runs after this stage
```

The V1 pipeline (`plan → produce → review`) becomes one instance of a general sequence, not the shape. Resume-after-decision addresses a **stage index**, not a role name, because the same role may appear more than once.

**Built in Sprint 9** as `TEMPLATE.pipeline: tuple[StageSpec, ...]` (`app/templates/software_company.py`). The `software_company` template still ships exactly the 3-stage `plan → produce → review` shape this sprint — `kind` (`"discuss"` is not yet a real stage kind; PM↔CTO discussion is Sprint 12) drives the engine's per-stage event/side-effect dispatch generically, so adding a stage (a second `produce` role in Sprint 11, a `discuss` kind in Sprint 12) is template data, not an engine change. Verified by a test-only 4-stage pipeline (`tests/test_pipeline_stages.py`) built from the real template's three roles, with `produce` appearing twice.

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
| `workflow_engine` | The brain. Iterates `TEMPLATE.pipeline` (plan → produce → review for the real template) as background asyncio tasks, dispatching per-stage by `kind` (§4.1). Parses FILE blocks, commits to the mission branch, runs matched `CheckSpec`s through `SandboxRunner`, hands the Reviewer a Change Summary + real diff + checks summary. Approve → merge; reject → branch preserved; request_changes → resumes at the first `produce` stage index; merge conflict → `blocked` with a plain-language reason. Orphan recovery, cancel, and a per-mission budget guard run around it (Rule #13). | ✅ Template-driven stage sequence, `TaskSnapshot`-based (Sprint 9) |
| `agent_runtime` | Employee state + validated transitions. Founds Employees with role-keyed defaults (`AgentORM.role_key`). Idle-first Role → Employee resolution with an `AGENT_RESOLVED` event. | ✅ Role/Employee split — Sprint 10; CTO/multi-role expansion — Sprint 11 |
| `templates` | Static internal data file (`app/templates/software_company.py`). Single source of the founding trio, `TEMPLATE.pipeline` stage sequence (§4.1), `RoleSpec` (contract/tools/permissions/category/singleton/description/default_profile), founding profile defaults, onboarding data, `CheckSpec`s. | ⚠️ **`tools`/`permissions` declared but empty (no real grants); no approval-flow or template registry** — Sprints 11, 19 |
| `agent_profiles` | CEO-editable personality / working style / decision style / custom instructions / per-Employee model override, persisted as JSON on `AgentORM.profile`. | ✅ |
| `prompt_builder` | Pure function: profile + role → system prompt. Role contract appended **last**, so no custom instruction can suppress the Reviewer's trailing `**Verdict:**`. | ✅ |
| `provider_gateway` | Sole path to AI. `MockProvider` (default, zero-key) + `AnthropicProvider` (streaming, retry-with-backoff). Three-tier model resolution: Employee override > CEO per-role override > registry default. | ✅ |
| `model_registry` | Logical refs (`planner-default`, `builder-default`, …) → (provider, model). | ✅ |
| `costs` | Per-call token usage → USD. Payroll (monthly, per company + per Employee) and Mission Budget (all-time, per mission), with a `usage_for_task` lookup the engine's budget guard checks before every stage. | ✅ Enforcement added (Sprint 9, Rule #13) |
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
| `auth` | Local email+password accounts. `IdentityProvider` port + `LocalIdentityProvider`; bcrypt (cost 12) password hashing, no plaintext column anywhere; HttpOnly session cookies, SHA-256 token hash at rest, sliding 7-day expiry / 30-day max age; `register`/`login`/`logout`/`me` routes; `get_current_user` dependency applied to every non-health/non-auth router. | ✅ Sprint 9 |
| Roles API | `GET /api/projects/{id}/roles` — read-only, template-owned Role data (`key`/`title`/`category`/`singleton`/`description`); no write route, Role is not CEO-owned. Lives in `projects` module, not a standalone `roles` module. | ✅ Sprint 10 |
| `specifications`, `memory`, `widgets` | — | 🔲 **Do not exist** — Sprints 12–18 |

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

Identified by code review at the V1.1 planning gate; **all five items closed in Sprint 9**:

1. ✅ **Orphaned missions.** Fixed (Phase 1): `lifespan` sweeps `in_progress`/`in_review` Tasks at boot and blocks them with a `TASK_RECOVERED` event; `POST /api/tasks/{id}/cancel` + an in-memory `_running` registry give the CEO a live cancel path. The same sweep also frees the Employee that was mid-pipeline on that Task — found missing during Phase 5's own DoD verification (the Agent was otherwise left parked in a busy `AgentState` forever, crashing the next Mission ever assigned to it); it's walked back to `idle` through `AGENT_TRANSITIONS`, one `AgentStateChanged` event per Employee. See `docs/DECISIONS.md` #162.
2. ✅ **No budget enforcement.** Fixed (Phase 1): `_check_budget` runs before every pipeline stage against `commander_mission_max_tokens`/`_usd`/`_seconds`; exceeding any cap blocks the mission and publishes `BUDGET_EXCEEDED` instead of continuing to spend.
3. ✅ **Detached ORM reuse.** Fixed (Phase 1): `TaskSnapshot` (frozen dataclass) is read once per pipeline run and threaded through stages instead of a detached `TaskORM`; `dataclasses.replace` re-syncs it after the one field a stage legitimately mutates (`branch_name`).
4. ✅ **Positional role unpacking.** Fixed (Phase 2): `TEMPLATE.pipeline: tuple[StageSpec, ...]` replaces `_PM, _ENGINEER, _REVIEWER = TEMPLATE.roles`; the engine iterates the sequence generically by stage `kind`, and `resume_from` addresses a stage **index** rather than a role_key so the same `kind` can repeat. See §4.1.
5. ✅ **Sandbox hardening gaps.** Fixed (Phase 0): `--cap-drop ALL` and `--security-opt no-new-privileges` added to `docker create`; `--read-only` deliberately omitted since checks write build/cache output under `/workspace` (see `docs/DECISIONS.md`).

---

## 7. Security Model

### 7.1 Execution — what runs, and what never does

- **The command is never AI output.** `CheckSpec.command` (e.g. `pytest`, `node --test`) is trusted data in the template. The Employee's output — deliverable, FILE blocks, prose — is never parsed for commands and never reaches a shell. Only the *presence* of matching files (`detect_globs`) selects which fixed commands run.
- **Isolation, per run:** fresh container → tar-copy the landed branch files in → run one fixed command → capture output tail → destroy unconditionally, even on failure or timeout. No container is reused.
- **Constraints:** no network (`--network none`), memory / CPU / PIDs caps, non-root user, 120s hard kill-and-reap, `--cap-drop ALL` and `--security-opt no-new-privileges` (Sprint 9). `--read-only` is deliberately not set — checks need to write under `/workspace` (build artifacts, `__pycache__`, test caches).
- **Fails closed, never open:** Docker missing, image absent, check timed out, or CEO toggle off → no-op (`check_results: null`, zero events). It never falls back to running anything unsandboxed. Capability is probed live, never assumed.
- **The harness changes none of this.** When agents gain tool loops (Sprint 16), the only execution tool is `run_checks`. There is no path by which an agent obtains a shell, and blocklists are never accepted as a substitute for the whitelist (Rule #12).

### 7.2 Authorization  *[V1.1 — Sprint 9 ✅]*

- Session-cookie authentication (HttpOnly, `samesite=lax`), session tokens stored as SHA-256 hashes, sliding 7-day expiry capped at a 30-day absolute max. `commander_cookie_secure` gates the `Secure` flag (off for local http dev; a real deployment behind TLS must set it, or the browser drops the cookie).
- Every Company has an `owner_id`; `get_current_user` is a dependency on every router except `health` and `auth` itself.
- Cross-account access returns **404, not 403** — existence is not disclosed (Rule #15). Enforced by `core/ownership.py`'s `project_owned_by` (direct) and `resource_owned_by` (generic, any ORM row with a `project_id` column — covers Task/Approval/Agent/Report without per-type duplication).
- Password hashes only (bcrypt, cost 12); no plaintext column exists anywhere in the schema. `scripts/export_users.py` never touches `password_hash`.
- The identity provider is an interface (`IdentityProvider`) with one implementation (`LocalIdentityProvider`, email+password); adding Google OAuth is one new file, not a refactor — the schema already carries the optional `provider_subject` column, NULL for local accounts.
- The SSE `/stream` route authenticates the same way as any other route (session cookie), which is *why* sessions are cookies and not a bearer token in the first place — `EventSource` cannot set custom headers.
- New Sprint 11 routes (`POST /api/projects/{id}/agents`, `GET /api/projects/{id}/skill-templates`, extended `PUT /api/agents/{id}/profile`) follow this same rule with no exception: `project_owned_by`/`resource_owned_by` → 404, never a bespoke auth path.

### 7.3 Singleton hiring concurrency  *[V1.1 — Sprint 11 ✅]*

Sprint 10 deferred the singleton-role TOCTOU risk because no reachable
mutation existed yet (`create_employee` was not exposed through a route).
Sprint 11's hiring route made the race real, so it is closed at the
database layer rather than in application code:

- `role_singleton_locks` (`project_id`, `role_key` composite primary key, `agent_id`, `created_at`) holds exactly one row per `(project, singleton role_key)` that is currently occupied.
- `hire_employee` inserts the new `AgentORM` row and, for `role.singleton is True`, the matching lock row **in the same transaction**. Founding (`create_department`) does the same for the founding PM/Reviewer, so a freshly created company never has a singleton Employee without a corresponding lock row (see `docs/DECISIONS.md` #183 — a gap that would otherwise let the *first* post-founding hire for `"pm"` slip through).
- Two concurrent `hire_employee` calls for the same `(project_id, role_key)` both attempt the insert; the database's own primary-key uniqueness constraint — not a service-layer check-then-insert — allows exactly one to commit. The loser's `IntegrityError` is caught and converted to `SingletonRoleViolation` → HTTP 409.
- This guarantee is per-database-engine agnostic in intent (Postgres row-level MVCC settles the race directly; the SQLite test harness additionally needs an explicit `busy_timeout` so the losing writer reaches the same `IntegrityError` instead of an unrelated `database is locked` error — a test-harness-only concern, see `docs/DECISIONS.md` #184).
- The lock table's protection is derived from `RoleSpec.singleton`, not a hardcoded set of role keys — a new singleton Role added purely as template data (e.g. a future Designer lead) is automatically protected with zero engine changes.
- No employee-firing flow exists yet, so lock rows are never deleted once created; this is an accepted Sprint 11 scope boundary, not an oversight (see §9 Out of Scope in `docs/prompts/sprint-11.md`).

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

**Auth (Sprint 9 ✅):** every API call sends `credentials: "include"`; a plain React `AuthProvider` context (mirroring `RealtimeProvider`'s pattern, not a state library) holds the current user and is mounted once in `Providers`. Any 401, from any request anywhere in the app, dispatches a `commander:unauthorized` `window` event that `AuthProvider` alone listens for — clearing local state and redirecting to `/login`, decoupling `lib/api.ts` from React/router. `RequireAuth` gates `/` and `/company/[id]` (and everything under it); `/login` and `/register` are the only unauthenticated routes. Per brief §2.11, the top-right `AccountBadge` is a single click-to-sign-out control, deliberately not a dropdown; a separate email + "Sign out" row lives in the Sidebar footer.

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
