# CLAUDE.md — Commander

Commander is an operating system where a solo developer becomes the **CEO of an AI software company**. AI agents work as Employees; the CEO instructs, observes, and decides. Sprint 3 shipped a working vertical slice: FastAPI backend + event bus + mock/Anthropic providers + SSE realtime + Next.js dashboard. Sprint 4 ("Real Intelligence") hardened the provider path (streaming, retries, real token usage) and added CEO-facing levers on top of it: Payroll, per-role model reassignment, and the Daily Report. Sprint 4.5 ("Employee Profiles") let the CEO customize each Employee's personality/working style/decision style and give per-Employee custom instructions and a model override, all flowing into the actual system prompt via `prompt_builder`. Sprint 4.7 ("Headquarters UX") applied `docs/design/UX_SPEC.md`'s core: unified status vocabulary, the Decisions and Timeline pages, a reworked decision-first Headquarters, upgraded My Companies cards, onboarding (Employee intros + starter Missions), and an internal-only `software_company` template (§10.6) that the founding trio, workflow order, and role contracts now read from instead of holding their own hardcoded copies. Sprint 5 ("Workspace") gave Employees a real git-backed workspace: `deliverable_type: "code" | "document"` missions, an Engineer FILE-block contract parsed and committed to a mission branch, CEO review as Change Summary + real (truncatable) diff — never raw deliverable text — and a Workspace page for browsing the company's actual codebase, all under an absolute gate: no AI-generated code is ever executed. Sprint 6 ("Execution Sandbox") opened exactly one controlled exception to that gate: after the Engineer's code lands on the mission branch, the template's trusted, never-AI-authored `CheckSpec` commands (not the Engineer's own output) run inside an isolated, no-network, resource-capped, non-root, auto-destroyed Docker container, and the results feed the Reviewer's context and the CEO Decision as another verdict chip — failing closed (silent no-op, `check_results: null`, zero events) whenever Docker/the sandbox image is unavailable or the CEO has the per-company toggle off. Sprint 7 ("V1 Hardening & Dockerized Postgres") is a **hardening sprint, not a feature sprint**: it made Postgres (via Docker Compose) the default datastore with Alembic-owned migrations, verified the provider/error path against the real Anthropic API (CEO-legible errors, no leaked tracebacks, `parse_verdict` fixed to take the trailing — not first — `**Verdict:**` line), and added operational surface: `/api/health` + `/api/health/db` (liveness vs. readiness), fail-fast boot config validation (`core/boot_checks.py`), and frontend resilience (API-down banner, SSE "Reconnecting…" indicator). It touched no product features. Sprint 8 ("V1 Release") is a **polish/coherence/packaging sprint, not a feature sprint**: it closed the "does this hang, mislead, or lie" gaps across all 10 routes (empty/loading/error states, loading-vs-not-found conflation, a Commander-voiced `ErrorState` everywhere `isError` was previously unhandled), added an always-visible "Simulation mode" signal plus strengthened mock-provider honesty language so demo output never reads as more real than it is, and packaged the repo for a cold read (`make help`, `make demo`, a README front door with verified verbatim commands and an explicit sandbox-optionality statement, `.gitignore`/tree cleanup). It touched no product features either — see the V1/V1.5 boundary note below. **v1.0.0 is tagged as of Sprint 8's completion.**

**V1 / V1.5 boundary:** everything above (through Sprint 8 / `v1.0.0`) is V1 — a hardened, coherent, working vertical slice on real infrastructure. V1.5 concepts (Agent Harness, a CTO agent, PM Specification, Project Memory, a requirement-change flow, `EngineerWorker`/`ClaudeCodeWorker` interfaces) are **not built and must not be added without an explicit sprint brief** — the Engineer stays single-shot exactly as-is. Do not blur this line "while you're in there."

## Product Terminology (MANDATORY in all UI text)

Code/DB/API use internal terms. UI labels, page titles, toasts, empty states use Commander terms. Never leak engineering jargon to the CEO.

| Internal (code) | UI (Commander) |
|---|---|
| Project | Company |
| User | CEO |
| Repository | Workspace |
| Task | Mission |
| Issue | Risk |
| Chat | Meeting |
| Agent | Employee |
| Agent Group | Department |
| Dashboard | Headquarters |
| Log | Timeline |
| Configuration | Company Settings |
| Deployment | Launch |
| Review | Audit |
| Approval | CEO Decision |

## Hard Architecture Rules (never violate)

1. Modules never import each other's internals — cross-module communication goes through the **EventBus**.
2. Agents never talk to each other directly — only via events.
3. Every significant action emits an event; every agent action carries a `reason` string (observable + explainable).
4. AI providers are never hard-coded. All model calls go through **ProviderGateway**; logical model refs resolve via `model_registry`.
5. Layering: Events → Domain Modules → Workflow → API. No circular deps.
6. The product must fully work with `COMMANDER_PROVIDER=mock` and **zero API keys**. Never break mock mode.
7. Secrets are read only through `SecretsProvider` (`core/secrets.py`). Never log secret values, never echo keys back through the API.
8. Timeline is a **single event stream**; `kind: "system" | "conversation"` distinguishes rendering, not storage.

## Repo Layout

```
apps/api/          FastAPI backend (Python 3.11+, async SQLAlchemy, Postgres default/SQLite tests)
  app/core/        events (schemas), interfaces (ports), lifecycle (state machines), db, secrets,
                   config, boot_checks (fail-fast startup validation)
  app/templates/   software_company.py — internal-only template: founding trio, pipeline order, role
                   contracts, default profiles, onboarding intros/starters. Single source, no picker.
  app/modules/     projects, tasks, approvals, timeline, agent_runtime, agent_profiles, prompt_builder,
                   workflow_engine, event_bus, provider_gateway, model_registry, costs, reports,
                   situation, realtime (SSE), workspace_manager (git-backed company codebase),
                   sandbox (Docker-isolated execution of trusted, template-defined checks)
  alembic/         async migration environment; alembic/versions/ holds the schema history
  tests/           pytest suite
apps/dashboard/    Next.js App Router + TS + Tailwind + TanStack Query (dark Render-style theme)
packages/event-schemas/ts/   generated TS event types — DO NOT hand-edit; regenerate
scripts/           generate_ts_schemas.py, seed.py, verify_real_llm.py
docs/              ARCHITECTURE.md (as-built), DECISIONS.md (judgment log), backend/ specs
docs/design/UX_SPEC.md   product experience source of truth — ALL frontend work follows it
docs/prompts/      sprint briefs
```

## Commands

```bash
make install      # api deps (pip -e) + dashboard deps (pnpm)
make db-up        # start Postgres (docker compose), wait for healthy
make db-down      # stop Postgres
make db-upgrade   # run Alembic migrations to head
make db-downgrade # roll back one migration
make seed         # db-up + db-upgrade, then reset DB, found demo company "Acme AI"
make dev          # db-up + db-upgrade, then api :8000 + dashboard :3000
make test         # pytest (apps/api) + dashboard typecheck + dashboard build
make verify-llm   # one real Mission against a live Anthropic key + throwaway DB
python scripts/generate_ts_schemas.py   # after ANY event schema change
```

## Conventions

- Event contracts: single Pydantic v2 `Event` envelope + per-type payload models in `PAYLOAD_MODELS`, validated by `build_event()`. Adding an event type = enum entry + payload model + regenerate TS.
- State machines: `core/lifecycle/` owns Agent/Task states and legal transitions. Never mutate state fields directly — go through `transition()` so the change is validated and emitted.
- Each workflow step opens its own DB session; don't hold sessions across sleeps/awaits on the provider.
- Frontend: server data via TanStack Query; SSE events dedup by `event.id` and invalidate queries (`invalidateForEvent`). Generated types from `packages/event-schemas/ts` — never redeclare event shapes.
- Reviewer verdicts are parsed from a trailing `**Verdict:** ...` line — provider-agnostic; workflow never branches on provider.
- Code missions: one real git repo per company at `${COMMANDER_WORKSPACE_ROOT}/{project_id}`, branch-per-mission (`mission/{task_id[:8]}`). Engineer output is parsed for `===== FILE: path =====` blocks and a `**Change Summary:**`; zero valid blocks falls back to a document mission rather than failing. Reviewer audits the diff statically; the Engineer's own output is never executed or shelled out to. The only code that ever runs is the template's trusted, fixed `CheckSpec` commands, inside `sandbox`'s isolated Docker container, against the already-committed file tree — see `docs/ARCHITECTURE.md`'s Security Model section before touching anything in `modules/sandbox`.
- Commit style: `feat(scope): ...` / `fix(scope): ...` / `docs: ...` / `chore: ...`. Commit per meaningful unit.
- Every non-obvious judgment call gets one entry in `docs/DECISIONS.md`.

## Current Status (post-Sprint 8, V1 released — `v1.0.0`)

Working: company CRUD + auto-founded 3 Employees (PM/Engineer/Reviewer) reading from the internal `software_company` template, Mission kanban, PM→Engineer→Reviewer pipeline with streaming replies and retry-with-backoff, CEO Decisions page (Pending/History tabs, full DecisionCard anatomy: Problem/Recommendation/Risk/Impact + reviewer attribution), unified Timeline page (CEO/Technical toggle, filters, digest grouping, cursor pagination) + SSE live feed, Meeting chat, Company Settings with runtime API-key entry and per-role model reassignment, Payroll (real token usage → USD, company + per-Employee + per-Mission), on-demand CEO Daily Report (trailing-24h executive summary, now its own `/reports` page), on-demand Situation Report (`GET /projects/{id}/situation`, PM-voiced glanceable status), a reworked decision-first Headquarters (decision strip hero → situation report → linked Vitals → condensed Timeline), a unified status-vocabulary token shared by every card/badge/column, onboarding (founding purpose field → live Mission, per-Employee intro events in the Timeline, one-click starter Missions), seed/demo mode, Employee Profiles (CEO-editable personality/working-style/decision-style + up to 500-char custom instructions + per-Employee model override; three-tier model resolution is agent override > CEO per-role override > registry default; the Reviewer's role contract is appended last by `prompt_builder` and survives any custom instruction), a real git-backed Workspace (Sprint 5): `deliverable_type` code missions land the Engineer's FILE-block output on a per-mission branch via `LocalGitWorkspaceManager`, the CEO reviews a Change Summary + real (truncatable) diff — never raw deliverable text — via `ChangeSummaryCard`, approval merges the branch (`branch.merged`), and a Workspace page browses the company's actual file tree/file contents/merge history — and an Execution Sandbox (Sprint 6): after the Engineer's code lands, the template's trusted `CheckSpec`s (pytest / node-test / python-syntax) that match the landed file tree run inside an isolated `DockerSandbox` (no network, resource-capped, non-root, 120s kill, always destroyed) before the Reviewer sees the diff; results surface as chips on `ChangeSummaryCard`/`DecisionCard`/Timeline (`ExecutionResults`, per-check `ExecutionRow` in Technical view) and a Company Settings toggle lets the CEO turn checks off per company. `GET /api/system/capabilities` probes Docker live; everything degrades silently (zero events, `check_results: null`) without Docker Desktop or the sandbox image, so mock mode and Docker-less dev are unaffected. No AI-generated code is ever executed outside that one sandboxed, trusted-command path.

Sprint 7 ("V1 Hardening & Dockerized Postgres") hardened this slice without adding product surface: Postgres (via `docker-compose`) is now the default datastore, schema owned by Alembic (`make db-up` / `db-upgrade` / `db-downgrade`; SQLite remains for tests); the provider/error path was verified live against the real Anthropic API (`_legible_error()` in `anthropic_provider.py` turns raw 401/403s into CEO-legible messages naming Company Settings, `parse_verdict` now takes the trailing `**Verdict:**` line instead of the first) and `scripts/verify_real_llm.py` (`make verify-llm`) runs one real Mission end-to-end against a throwaway DB; `GET /api/health` (liveness) and `GET /api/health/db` (readiness, real DB round-trip, `503` on failure) back a boot-time fail-fast config validator (`core/boot_checks.py`) and a dashboard `ApiStatusBanner` + SSE "Reconnecting…" pill (`useRealtimeConnectionStatus`); a data-safety audit confirmed zero destructive operations are reachable from any live API route (soft-delete/`archived` only; hard deletes exist only in `scripts/seed.py` and Alembic `downgrade()`, both CLI-only).

Sprint 8 ("V1 Release") is the final V1 sprint — coherence, demo honesty, and packaging, no new product surface. Every one of the 10 dashboard routes now handles TanStack Query's `isError` with a Commander-voiced `ErrorState` (previously unhandled anywhere); Mission detail / Employee profile / Report detail no longer conflate "still loading" with "doesn't exist"; the Employees grid and kanban columns got real empty states instead of a blank screen or one generic string. A persistent amber "Simulation mode" badge (Sidebar + `CompanyCard`) appears whenever a Company runs on the mock provider, and the mock provider's own revision summaries and Reviewer audit text now say outright that they're simulated, scripted output — Payroll's mock-mode dollar figures are pre-existing, deliberately-tested (Sprint 4) fabricated-but-labeled numbers, not a bug (see DECISIONS #125). Packaging: `make help` (self-documenting Makefile) and `make demo` (one-command `seed` + `dev`), a README front door with prerequisites that separate required Docker (Postgres) from optional Docker (the execution sandbox) and an explicit sandbox-degrades-gracefully statement, `.claude/scheduled_tasks.lock` untracked/gitignored, and an accidental duplicate-content commit in a sprint-brief doc reverted. Release verification (Phase 4): full test/typecheck/build green, a full mock-mode Mission driven end-to-end against a fresh Postgres volume via the live API (create → assign → plan → build → checks → review → CEO Decision → merge → completed, Payroll/Timeline/Situation Report all cross-checked coherent) — see DECISIONS #126–127. Tagged `v1.0.0`.

Not built yet (do NOT add without an explicit sprint brief): auth, hosted/remote cloud runner (beyond the local Docker sandbox), deployment/Launch, multi-provider beyond Anthropic+mock, and all V1.5 concepts (Agent Harness, CTO agent, PM Specification, Project Memory, requirement-change flow, `EngineerWorker`/`ClaudeCodeWorker` interfaces) — the Engineer stays single-shot exactly as-is until an explicit V1.5 brief says otherwise.

Known accepted MVP tradeoffs: plaintext secrets, in-process event bus (single worker), inline subscriber execution in `publish`, Python-side conversation filtering, no connection pooling/read replicas/backup tooling (single local Postgres container assumed). See `docs/DECISIONS.md` before "fixing" any of these.

## Working Style

- Work autonomously; when a brief leaves something open, make the reasonable call, log it in `docs/DECISIONS.md`, keep moving.
- Spec wins over legacy skeleton code — refactor, don't work around.
- Prefer boring, reliable choices. If a library fights you for >10 minutes, replace it.
- Self-verify before finishing: `make test`, `pnpm build` (dashboard), and boot the slice when behavior changed.
- Keep this file in sync: any architecture change must update CLAUDE.md and ARCHITECTURE.md in the same PR/commit. Desync is an architecture violation.
- Maintain PROGRESS.txt per the live progress discipline (see docs/prompts/) — update per item, never batched.
- Every sprint's final phase commit must be followed by `git push`; a sprint is not complete until the remote HEAD matches the final commit.