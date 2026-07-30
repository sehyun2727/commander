# CLAUDE.md — Commander

> **Commander is not a program that gives work to AI.**
> **Commander is an operating system for running an AI company.**
>
> When a design question has no obvious answer, the tiebreaker is always: *what would a real company do?*
> Why does the CEO only talk to the PM? Because it's a company.
> Why do Engineers never talk to the CEO? Because it's a company.
> Why does the PM raise approval requests? Because it's a company.
> Why does the Timeline exist? Because it's a company.
> Why does the dashboard look like Render? Because you're operating a company, not chatting.
>
> This philosophy outranks any individual feature.

**Status: V1 released (`v1.0.0`, Sprint 8). V1.1 in development.**
This file describes both what exists today and what V1.1 is building toward. Sections marked **[V1.1 — not built]** must not be implemented without an explicit sprint brief.

---

## 1. What Commander Is

A solo operator becomes the **CEO of an AI software company**. AI Employees do the work; the CEO sets direction, reads reports, and decides.

The competitive claim is not a better coding agent. It's the **organization layer** sitting on top of replaceable workers: a full company workflow (CEO → PM ⇄ CTO → Employees → Reviewer) with accountability, memory, and delegation. Cursor and Claude Code are tools you drive — they stop when you stop, and the artifact is a diff. Commander is an organization you govern — it keeps working while you're away, and the artifact is an explained, accountable result.

## 2. Organization Model

Two different axes. Drawing them as one chart produces a contradiction — keep them separate.

**Decision axis (planning).** PM and CTO are peers.

```
                CEO
                 │
            (one channel)
                 │
        PM  ←── 협의 ──→  CTO
        business        technical
                 │
      Project Specification
                 │
           CEO approval
```

**Delegation axis (execution).** After approval, work descends.

```
        PM  ──assigns──▶  CTO  ──assigns──▶  Employees
                                                 │
                                             Reviewer
                                                 │
                                          PM judgment
                             Minor / Major / Critical → CEO only if Critical
```

### Roles vs Employees — the central V1.1 distinction **[V1.1 — not built]**

| | Owned by | Defines | Count |
|---|---|---|---|
| **Role** | the Template (immutable) | prompt contract · tool grants · permissions · workflow position · harness · default behavior | fixed by template |
| **Employee** | the CEO | name · AI model · individual profile | unlimited |

- **Leadership roles are singletons and permanent:** exactly one PM, one CTO, one Reviewer. Never zero, never two.
- **Worker roles are unlimited.** V1.1 ships Backend Engineer and Frontend Engineer. Designer / QA / DevOps / Security / ML Engineer / Data Analyst / Technical Writer are future roles the architecture must already accommodate — as *data*, not as code changes.
- **One role can hold many Employees**, each on a different model:
  ```
  Backend Engineer
    ├── Kim  (Claude Sonnet)
    └── Lee  (GPT-5.5)
  Frontend Engineer
    └── Park (Gemini)
  ```
  The PM assigns a Mission to a specific Employee, not to a role.
- **Employee creation flow:** Add Employee → select Role → select AI model → select skill template → create.

Pricing tiers may cap employee count later. The architecture must never assume a cap.

## 3. Product Terminology (MANDATORY in all UI text)

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
| Dashboard | CEO Workspace |
| Log | Timeline |
| Configuration | Company Settings |
| Deployment | Launch |
| Review | Audit |
| Approval | CEO Decision |
| Role definition | Position |
| Specification | Project Specification |
| Discussion | Meeting / 협의 |
| Memory | Company Knowledge |
| Budget | Resource Limit |
| Stage | 업무 단계 |
| Widget | Widget (CEO-facing term as-is) |

## 4. Hard Architecture Rules (never violate)

**#1–#10 are V1 rules, unchanged and non-negotiable. #11–#17 are added by V1.1.**

1. Modules never import each other's internals — cross-module communication goes through the **EventBus**.
2. Agents never talk to each other directly — only via events.
3. Every significant action emits an event; every agent action carries a `reason` string (observable + explainable).
4. AI providers are never hard-coded. All model calls go through **ProviderGateway**; logical model refs resolve via `model_registry`.
5. Layering: Events → Domain Modules → Workflow → API. No circular deps.
6. The product must fully work with `COMMANDER_PROVIDER=mock` and **zero API keys**. Never break mock mode.
7. Secrets are read only through `SecretsProvider`. Never log secret values, never echo keys back through the API.
8. Timeline is a **single event stream**; `kind: "system" | "conversation"` distinguishes rendering, not storage.
9. **No AI-generated code is ever executed outside the sandbox, and AI never chooses the command.** Commands are trusted template data; AI output is only ever input files.
10. Any architecture change updates **CLAUDE.md and ARCHITECTURE.md in the same commit.** Desync is an architecture violation.

**#11 — The CEO has exactly one conversational counterpart: the PM.**
There is no route through which the CEO messages an Engineer, the CTO, or the Reviewer. Not disabled — *absent*. The CEO's observation channel is the Timeline; the CEO's intervention channel is a CEO Decision. Everything else reaches the CEO through the PM.

**#12 — Tools are granted by the Template to a Role. Nobody else grants tools.**
Neither an Employee, nor the CEO, nor an agent's own output can add a tool. A Role's tool grants are a whitelist in template data. Even inside an autonomous loop, the only execution tool that exists is `run_checks` (template-defined commands, sandboxed). `execute_command` or any free shell is permanently rejected — blocklists always leak; only whitelists hold. This is rule #9 extended to the harness era.

**#13 — Every autonomous loop runs under a budget.**
Any looping subject — agent tool loops, PM↔CTO discussion, self-correction retries — has caps on iterations, tokens, wall time, and cost. Budget exhaustion is not an error; it is an organizational event: the Mission goes `blocked` with a reason, and the CEO is informed. Never silently stop, never retry forever.

**#14 — Project Memory is derived from the event stream.**
No second source of truth. Memory is an index/projection over events that already exist. If a fact isn't in the event stream, it isn't in the company's memory.

**#15 — Every data access is account-scoped.**
The only routes reachable without authentication are the health checks and the auth endpoints themselves. Every Company has an owner. Another account's data returns **404, not 403** — existence itself is not disclosed.

**#16 — Roles are data; Employees are instances.**
No component, prompt, or engine branch may test a hardcoded role name (`role == "engineer"`). Behavior comes from the Role definition the template supplies. Adding a role must never require touching the engine.

**#17 — New CEO-facing capability lands as either a Widget or a Sidebar page.**
Nothing new gets bolted onto the PM conversation area. This keeps the conversation the stable center of the experience and makes the surface predictable as the product grows.

## 5. Repo Layout

```
apps/api/          FastAPI backend (Python 3.11+, async SQLAlchemy, Postgres default/SQLite tests)
  app/core/        events (schemas), interfaces (ports), lifecycle (state machines), db, secrets,
                   config, boot_checks (fail-fast startup validation)
  app/templates/   software_company.py — the only shipped template. Owns: role definitions
                   (contract, tools, permissions, workflow position), pipeline stage sequence,
                   founding roster, default profiles, onboarding intros/starters, CheckSpecs.
  app/modules/     projects, tasks, approvals, timeline, agent_runtime, agent_profiles,
                   prompt_builder, workflow_engine, event_bus, provider_gateway, model_registry,
                   costs, reports, situation, realtime (SSE), workspace_manager, sandbox
                   [V1.1 adds] auth, roles, employees, specifications, memory, widgets
  alembic/         async migration environment; alembic/versions/ holds the schema history
  tests/           pytest suite
apps/dashboard/    Next.js App Router + TS + Tailwind + TanStack Query (dark Render-style theme)
packages/event-schemas/ts/   generated TS event types — DO NOT hand-edit; regenerate
scripts/           generate_ts_schemas.py, seed.py, verify_real_llm.py
docs/              ARCHITECTURE.md (target + as-built), DECISIONS.md (judgment log), backend/ specs
docs/design/UX_SPEC.md   product experience source of truth — ALL frontend work follows it
docs/prompts/      sprint briefs
```

## 6. Commands

```bash
make install      # api deps (pip -e) + dashboard deps (pnpm)
make db-up        # start Postgres (docker compose), wait for healthy
make db-down      # stop Postgres
make db-upgrade   # run Alembic migrations to head
make db-downgrade # roll back one migration
make seed         # db-up + db-upgrade, then reset DB, found demo company "Acme AI"
make dev          # db-up + db-upgrade, then api :8000 + dashboard :3000
make demo         # seed + dev, one command
make test         # pytest (apps/api) + dashboard typecheck + dashboard build
make verify-llm   # one real Mission against a live Anthropic key + throwaway DB
python scripts/generate_ts_schemas.py   # after ANY event schema change
```

## 7. Conventions

- Event contracts: single Pydantic v2 `Event` envelope + per-type payload models in `PAYLOAD_MODELS`, validated by `build_event()`. Adding an event type = enum entry + payload model + regenerate TS.
- State machines: `core/lifecycle/` owns Agent/Task states and legal transitions. Never mutate state fields directly — go through `transition()`.
- Each workflow step opens its own DB session; never hold an ORM object across an await on the provider. Pass immutable snapshots between stages, not detached ORM rows.
- Frontend: server data via TanStack Query; SSE events dedup by `event.id` and invalidate queries. Generated types only — never redeclare event shapes.
- Reviewer verdicts parse from a trailing `**Verdict:** ...` line — provider-agnostic; workflow never branches on provider.
- Code missions: one real git repo per company, branch-per-mission (`mission/{task_id[:8]}`). Engineer output is parsed for `===== FILE: path =====` blocks; zero valid blocks falls back to a document mission rather than failing. The only code that ever runs is the template's trusted `CheckSpec` commands inside the sandbox — read ARCHITECTURE.md's Security Model before touching `modules/sandbox`.
- Commit style: `feat(scope): ...` / `fix(scope): ...` / `docs: ...` / `chore: ...`.
- Every non-obvious judgment gets one entry in `docs/DECISIONS.md`.

## 8. Current Status — V1 As-Built (`v1.0.0`)

Shipped and working today:

- **Company + org:** company CRUD; founding auto-creates a Department with 3 Employees (PM / Engineer / Reviewer) from the internal `software_company` template, each with a default `AgentProfile` and an intro line posted to the Timeline. One-click starter Missions.
- **Pipeline:** PM → Engineer → (sandbox checks) → Reviewer, running as background asyncio tasks, publishing every beat. Streaming replies, retry-with-backoff.
- **Workspace:** a real git repo per company; code missions land the Engineer's FILE-block output on a mission branch; CEO reviews Change Summary + real (truncatable) diff, never raw deliverable text; approve merges the branch.
- **Execution sandbox:** template-defined `CheckSpec` commands run in an isolated Docker container (no network, resource-capped, non-root, 120s hard kill, always destroyed) against the landed file tree. Degrades to a silent no-op without Docker.
- **CEO surface:** Headquarters, Decisions (Pending/History, full DecisionCard anatomy), Missions kanban, Mission detail with Meeting transcript, Employees + profiles, Timeline (CEO/Technical toggle, filters, digest grouping, cursor pagination), Reports, Workspace browser, Company Settings.
- **Money & models:** real token usage → USD (Payroll per company / Employee / Mission); three-tier model resolution (Employee override > CEO per-role override > registry default).
- **Infra:** Postgres via Docker Compose with Alembic-owned schema (SQLite for tests), `/api/health` + `/api/health/db`, fail-fast boot validation, API-down banner, SSE reconnect indicator.
- **Honesty:** persistent "Simulation mode" badge whenever a company runs on mock; mock output states outright that it's scripted.

157 tests passing / 4 skipped as of `v1.0.0`.

### V1's deliberate limits (the reason V1.1 exists)

1. **The Engineer is a one-shot generator.** It does not read the existing repo, does not iterate, and does not fix itself when a check fails. Mission #2 does not know Mission #1 happened.
2. **The CEO's input is the development input.** There is no step that turns a vague instruction into a structured specification.
3. **The CEO stands inside the pipeline.** Every mission ends at a CEO Decision, and the CEO has three separate conversational counterparts.
4. **No memory, no learning, no accounts.**

## 9. V1.1 Scope **[not built — sprint brief required for every item]**

| Phase | Sprint | Delivers |
|---|---|---|
| A | 9 | Reliability foundation (orphan recovery, cancel, budget guard, snapshot pipeline) + accounts/auth |
| B | 10 | Role/Employee separation; roles become template data |
| B | 11 | CTO role; unlimited employees; multi-employee-per-role; employee creation flow |
| C | 12 | PM↔CTO discussion; Project Specification; Requirement Discovery; CEO pre-approval |
| D | 13 | CEO↔PM conversation backend; PM Report; decision authority classification |
| D | 14 | Render-benchmark UI shell; conversation-left / widget-dock-right layout |
| D | 15 | Widget system (add / remove / reorder) + initial widget set |
| E | 16 | Agent Harness (repo-aware tool loop under budget) |
| E | 17 | Self-correction loop |
| F | 18 | Project Memory + Sprint Learning |
| G | 19 | Mission Tree; remaining widgets; template registry cleanup |
| H | 20 | V1.1 release |

**Out of scope for all of V1.1:** shipping a second company template (the architecture must support it; only Software Company ships) · multi-user collaboration on one company · hosting/deployment/Launch · providers beyond Anthropic + mock · template marketplace · parallel Backend/Frontend execution (V1.1 is sequential) · implementing Designer/QA/DevOps/Security roles.

### V1 / V1.1 boundary

Everything in §8 is V1. Everything in §9 is V1.1 and **must not be added "while you're in there."** The Engineer stays single-shot until the Sprint 16 brief says otherwise. Roles stay as they are until Sprint 10. Do not blur this line — sprint boundaries are what make the roadmap mean anything.

One exception the roadmap itself makes: **Headquarters is absorbed into the CEO Workspace, not retained as a separate page.** §8's "CEO surface" list is a V1 as-built description and correctly still says Headquarters — that page is real today. But it does not survive into V1.1 as a Sidebar page; its four blocks (Decision strip, Situation Report, Vitals, Timeline excerpt) map onto the Pending Approvals widget, the PM Report, the Progress/Employees/Risks/Costs widgets, and the Timeline widget respectively (see `docs/ARCHITECTURE.md` §8 for the full mapping). This absorption is decided, not open for re-litigation in a later sprint brief.

## 10. Known Accepted Tradeoffs

Plaintext secrets · in-process event bus (single worker) · inline subscriber execution in `publish` · Python-side conversation filtering · no connection pooling / read replicas / backup tooling (single local Postgres assumed) · mock-mode Payroll figures are fabricated-but-labeled.

Read `docs/DECISIONS.md` before "fixing" any of these.

## 11. Working Style

- Work autonomously; when a brief leaves something open, make the reasonable call, log it in `docs/DECISIONS.md`, keep moving.
- Spec wins over legacy skeleton code — refactor, don't work around.
- Prefer boring, reliable choices. If a library fights you for >10 minutes, replace it.
- Self-verify before finishing: `make test`, `pnpm build`, and boot the slice when behavior changed.
- Keep CLAUDE.md and ARCHITECTURE.md in sync in the same commit as any architecture change.
- Maintain PROGRESS.txt per the live progress discipline — update per item, never batched.
- Every sprint's final phase commit must be followed by `git push`; a sprint is not complete until remote HEAD matches.