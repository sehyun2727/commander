# Changelog

Commander does not yet follow strict semantic-versioning cadence for every
internal change — this file tracks major released milestones. See
`docs/DECISIONS.md` for the full decision-by-decision history and
`PROGRESS.txt` for sprint-by-sprint implementation detail.

## v1.1.0 — Sprint 9 through Sprint 19

V1.1 is the "organization deepens" release: CEO accounts, a hireable CTO,
PM↔CTO planning, a CEO Workspace, an Agent Harness with self-correction,
Project Memory, and — this final sprint — a second real LLM provider,
minimum production observability, and the documentation a stranger needs
to actually run this thing.

**The `v1.1.0` git tag is the CEO's own call**, made after hands-on browser
verification — see `docs/DECISIONS.md`'s Sprint 19 close-out entry. This
changelog entry describes what Sprint 9–19 shipped; it does not itself
constitute the release.

### Breaking changes

- **Sprint 9 — new auth schema.** `users` and `sessions` tables are new;
  every Company gained an `owner_id`. Upgrading from pre-Sprint-9 data
  requires running the `fa793dce62cb_accounts_and_sessions` migration and
  manually attributing existing Companies to a CEO account — see
  `docs/DEPLOYMENT.md` §7.
- **Sprint 10 — `AgentORM.role_key` rename.** The prior ad-hoc role-string
  field was replaced by the Role/Employee split (`RoleSpec` template data
  vs. `Employee` CEO-owned instance) — any code or query referencing the
  old field name needs updating.

### Sprint 9 — Reliability + auth

- Local CEO accounts: email/password registration, HttpOnly session
  cookies, `RequireAuth` gating every route except `/login`/`/register`.
- Cross-account access returns 404, not 403 (Rule #15 — resource
  existence itself must not be disclosed).
- Orphan-recovery, cancellation, and Mission budget-guard reliability
  hardening for the background pipeline.
- Narrative pacing sleeps between pipeline beats for a more "alive"
  Timeline feel.

### Sprint 10 — Role / Employee separation

- `RoleSpec` (frozen, template-owned) split from `Employee` (CEO-owned
  instance) — the structural foundation for hiring multiple Employees per
  Role.
- Singleton enforcement for leadership Roles (PM, CTO, Reviewer).
- Idle-first Role → Employee resolution; a read-only Roles API.
- Automated guard (Rule #16) against hardcoded role-identity branches
  anywhere in the workflow engine.

### Sprint 11 — CTO + multi-employee + hiring

- First-class `cto` `RoleSpec` — a singleton, vacant/hireable at founding
  rather than auto-seeded.
- CEO-facing "Hire Employee" flow: hire multiple Employees into a worker
  Role, each with an independently configured model and skill template.
- Database-backed singleton lock (`role_singleton_locks`) making
  concurrent singleton hiring race-safe.
- Canonical, typed, server-owned skill-template registry.

### Sprint 12 — PM↔CTO planning + Project Specification

- PM↔CTO planning orchestration: a CEO request becomes a reviewable,
  versioned `Specification` document through a budgeted turn loop (fast
  agreement, clarification, or blocking-feasibility paths).
- CEO decision gate (approve / reject / request-revision / cancel) —
  only an approved Specification can create and assign a gated Mission.
- CEO-facing Specifications surface (Sidebar page, detail view, turn
  transcript, version history) — reached only through the PM, never a
  direct CTO channel (Rule #11).

### Sprint 13 — CEO Workspace backend projection

- A single server-derived `next_action` projection: what needs the CEO
  next, computed from event/state, not a second source of truth.

### Sprint 14 — CEO Workspace UI shell

- `/company/[id]` CEO Workspace: current focus, pending attention,
  planning/mission status, org headcount, recent activity — responsive
  down to mobile.

### Sprint 15 — Widget system

- CEO Workspace's optional sections become configurable per-Company
  widgets — reorder, hide, restore, persisted per CEO.
- Template/server-owned widget registry; no CEO-authored custom widgets
  (deliberate scope boundary).

### Sprint 16 — Agent Harness

- A budgeted (Rule #13) tool loop for the Engineer, wired into the
  produce stage — template-whitelisted tools only (Rule #12), executed
  only inside the sandbox (Rule #9).
- Durable audit table + coarse Timeline projection (security-audited).

### Sprint 17 — Self-correction

- Bounded (explicit retry/iteration budget) self-correction — no
  cross-Mission learning, termination-triggered, server-computed rollback.

### Sprint 18 — Project Memory + Sprint Learning

- Deterministic, PM-explicit-only recall (`app/modules/memory/`) —
  keyword/tag substring match with recency decay, no embeddings/RAG.
- `MEMORY_RECALLED` Timeline event; recall results surface only inside
  the PM↔CTO planning transcript, no dedicated CEO-facing UI (deliberate
  scope boundary — see `docs/KNOWN_ISSUES.md` §5).
- Operator-run backfill script (`scripts/backfill_memory.py`).

### Sprint 19 — V1.1 shipping: verification, observability, release

- **`OpenRouterProvider`** — a third first-party `ProviderGateway`
  implementation (built from scratch, not a subclass of
  `AnthropicProvider`), proving Rule #4 (providers are replaceable) in
  production. `COMMANDER_PROVIDER` now accepts `mock | anthropic |
  openrouter`; the existing three-tier model resolution (Employee
  override → CEO per-role override → registry default) works uniformly
  across all three.
- **Structured JSON logging** (`app/core/logging.py`) with per-request
  correlation IDs (server-issued UUID, never trusts a client-supplied
  header) and per-Mission `task_id`/`agent_id`/`project_id` contextvars
  propagated through `asyncio.create_task`. Secret-shaped field names are
  redacted defensively (see `docs/DECISIONS.md` #251 for a mid-sprint
  audit fix to this redaction).
- **`scripts/load_smoke.py`** — 4 load-smoke scenarios (sequential
  Missions, concurrent Companies/Missions with live SSE, hot-path query
  counts, Memory recall at scale) now form the documented safe operating
  envelope in `docs/KNOWN_ISSUES.md`. Building this surfaced and fixed
  two real concurrent-Mission races in `agent_runtime`/`workflow_engine`
  (see `docs/DECISIONS.md` #250).
- **`docs/DEPLOYMENT.md`** (new) + **`.env.production.example`** (new) —
  the first end-to-end deployment walkthrough, a production run recipe,
  optional nginx TLS example, backup/restore, and the v1.0.0 → v1.1
  upgrade path.
- **`docs/KNOWN_ISSUES.md`** (new) — every accepted tradeoff, every
  deferred scope boundary from Sprints 15–18, and the verified operating
  envelope, consolidated in one place.
- **Independent security audit** (dedicated agent) of every Sprint 19
  security-relevant surface — found and fixed one real gap (log
  redaction was exact-match instead of substring-match; see
  `docs/DECISIONS.md` #251).
