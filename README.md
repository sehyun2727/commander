# Commander

Commander is an operating system where a solo developer becomes the **CEO of an AI software company**. You never manage prompts — you found a Company, it auto-staffs with three AI Employees (PM, Engineer, Reviewer), you hand it Missions, and every action they take is visible, explainable, and reviewable before it lands.

Status: **V1** — a real, working vertical slice. FastAPI backend, Postgres-backed persistence with Alembic migrations, an event-driven core, mock and real (Anthropic) providers, an SSE-realtime Next.js dashboard, a real git-backed Workspace per company, and a sandboxed execution gate for automated checks.

---

## What it does

- **Found a Company** and it auto-staffs three Employees: a PM, an Engineer, and a Reviewer, each with an editable personality/working-style/decision-style profile.
- **Hand it a Mission.** The PM plans it, the Engineer implements it, and — for code Missions — the Engineer's output lands as a real commit on a per-Mission git branch. If the Company's template ships automated checks (pytest, `node --test`, etc.) that match the changed files, they run inside an isolated, no-network Docker sandbox before review. This step is entirely **optional**: without Docker running or the sandbox image built (`make sandbox-image`), or with the per-Company toggle off in Company Settings, Missions still run end-to-end exactly the same — they just skip straight to review with no check results, no errors, no degraded UI.
- **Review as CEO.** Every Mission that needs your sign-off becomes a Decision: Problem / Recommendation / Risk / Impact, plus — for code — a Change Summary and a real (truncatable) diff, plus check results if any ran. Approve, request changes, or reject.
- **Watch it happen.** A single Timeline (CEO view or Technical view) narrates everything as it happens over SSE — no polling, no refresh.
- **Stay in control of cost and models.** Payroll shows real token spend (company-wide, per-Employee, per-Mission). Any role's model can be reassigned per Company; any Employee's model can be overridden individually.

None of the AI's own generated code is ever executed, installed, or shelled out to — the one exception is a fixed, trusted, non-AI-authored set of check commands (defined by the Company's template, not the Employee), run inside a locked-down, disposable Docker container. See `docs/ARCHITECTURE.md`'s Security Model section for the full detail.

---

## Quickstart

**Prerequisites:** Python 3.11+, Node.js + [pnpm](https://pnpm.io), and [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running) — Docker is **required** to run Postgres, the default datastore. It's also used for one **optional** feature, the execution sandbox (see below); everything else works without it.

```bash
make install   # api deps (venv + pip -e) + dashboard deps (pnpm)
make seed      # starts Postgres via Docker, runs migrations, seeds a demo company
make dev       # api on :8000, dashboard on :3000
```

(Or run `make demo` for `seed` + `dev` in one command.)

Then open **http://localhost:3000**. You'll see "Acme AI", a seeded demo Company with its three Employees and a couple of Missions already in flight, run entirely against the mock provider (zero API keys, zero cost).

`make seed` and `make dev` both depend on `db-up` (starts/waits on the `docker-compose` Postgres service) and `db-upgrade` (runs Alembic migrations to head), so there's no separate database setup step — the two commands above are the entire quickstart.

To start from a truly empty Commander instead of the seeded demo, skip `make seed` and just run `make db-up db-upgrade`, then `make dev`, and found your first Company from the dashboard's landing page.

### A first walkthrough

1. On `/`, found a Company — give it a name and, optionally, a sentence about what it should build. If you fill in the second field, Commander skips straight to a live starter Mission instead of an empty kanban.
2. Land on Headquarters (`/company/[id]`). You'll see your three Employees introduce themselves in the Timeline, a Decision strip (empty until something needs you), and a PM-voiced Situation Report.
3. Open **Missions**, create one (or use a one-click starter), and assign it. Watch the PM → Engineer → Reviewer pipeline run live — streaming replies, then (for code Missions) a real commit on a mission branch, then automated checks if the template has any that match, then a Reviewer verdict.
4. When it reaches **Decisions**, review the Change Summary and diff (never raw deliverable text), then Approve, Request changes, or Reject. Approving a code Mission merges its branch.
5. Browse the Company's actual codebase under **Workspace**, check **Payroll** for real token spend, and pull an on-demand **Daily Report** or **Situation Report** any time.

---

## Mock vs. real providers

Commander works completely with **zero API keys** — `COMMANDER_PROVIDER=mock` is the default and every feature above (including checks and diffs) works fully against a deterministic mock provider. This is also what CI and `make seed` use.

To use real Anthropic models instead:

1. Set `COMMANDER_PROVIDER=anthropic` and `ANTHROPIC_API_KEY=sk-...` in `.env` (copy `.env.example` first) — or leave both unset and paste the key into a Company's Settings page at runtime instead (it's stored write-only, never echoed back).
2. Restart the API. Commander validates this at boot: if `COMMANDER_PROVIDER=anthropic` with no key anywhere, it fails fast with a plain-language error before accepting any traffic, instead of failing confusingly on the first Mission.
3. Any role (Planner/Builder/Reviewer) can be reassigned to a specific Anthropic model per Company from Company Settings; any individual Employee can override its own model from its profile.

A missing/invalid key, or a 429/5xx from Anthropic, surfaces as a CEO-legible error on the Mission (e.g. "your Anthropic API key looks invalid — check Company Settings") — never a raw stack trace, and 429/5xx are retried with backoff before that happens.

To sanity-check a real key end-to-end outside the dashboard: `make verify-llm` runs one real Mission against a throwaway database and reports pass/fail plus actual token cost.

---

## Commands

```bash
make help         # list every command below with a one-line description
make install      # api deps (pip -e) + dashboard deps (pnpm)
make db-up        # start Postgres (docker compose), wait for healthy
make db-down      # stop Postgres
make db-upgrade   # run Alembic migrations to head
make db-downgrade # roll back one migration
make seed         # db-up + db-upgrade, then reset DB and found demo company "Acme AI"
make dev          # db-up + db-upgrade, then api :8000 + dashboard :3000
make demo         # seed + dev in one command — the fastest way to see Commander running
make test         # pytest (apps/api) + dashboard typecheck + dashboard build
make sandbox-image  # build the Docker image used for automated checks — optional (Sprint 6)
make verify-llm    # one real Mission against a live Anthropic key + throwaway DB
```

---

## Health checks

- `GET /api/health` — liveness only, no dependencies, always `200` once the process is up.
- `GET /api/health/db` — readiness: a real round-trip against the configured database, `200` or a clean `503` if the database is unreachable (e.g. Postgres is down).

The dashboard polls `/api/health` and shows a banner if the API is unreachable; the SSE connection has its own "Reconnecting…" indicator if the live event stream drops.

---

## Architecture at a glance

FastAPI + async SQLAlchemy backend, Postgres (via Docker) as the default datastore with SQLite as a zero-dependency fallback for tests, Alembic migrations, an in-process EventBus as the only channel between modules (agents never talk to each other directly — only via events), a ProviderGateway so no model is ever hard-coded, and a Next.js/TanStack Query dashboard driven by REST + one SSE stream per Company.

Full detail — module map, event contracts, lifecycles, the sandboxed execution security model, and every deliberate MVP tradeoff — lives in `docs/ARCHITECTURE.md`. Non-obvious judgment calls are logged as they're made in `docs/DECISIONS.md`.

---

## Repo layout

```
apps/api/          FastAPI backend (Python 3.11+, async SQLAlchemy, Postgres/SQLite)
  app/core/        events (schemas), interfaces (ports), lifecycle (state machines), db,
                   secrets, config, boot_checks (fail-fast startup validation)
  app/templates/   software_company.py — internal-only template: founding trio, pipeline
                   order, role contracts, default profiles, onboarding intros/starters
  app/modules/     projects, tasks, approvals, timeline, agent_runtime, agent_profiles,
                   prompt_builder, workflow_engine, event_bus, provider_gateway,
                   model_registry, costs, reports, situation, realtime (SSE),
                   workspace_manager (git-backed company codebase),
                   sandbox (Docker-isolated execution of trusted, template-defined checks)
  alembic/         async migration environment; `alembic/versions/` holds the schema history
  tests/           pytest suite
apps/dashboard/    Next.js App Router + TS + Tailwind + TanStack Query (dark Render-style theme)
packages/event-schemas/ts/   generated TS event types — do not hand-edit; regenerate
scripts/           generate_ts_schemas.py, seed.py, verify_real_llm.py
docs/              ARCHITECTURE.md (as-built), DECISIONS.md (judgment log), backend/ specs
docs/design/UX_SPEC.md   product experience source of truth
docs/prompts/      sprint briefs
```

---

## Product terminology

The UI speaks Commander's own vocabulary; the code speaks conventional engineering terms. If you're reading code and UI side by side: Project↔Company, User↔CEO, Repository↔Workspace, Task↔Mission, Issue↔Risk, Chat↔Meeting, Agent↔Employee, Dashboard↔Headquarters, Log↔Timeline, Configuration↔Company Settings, Review↔Audit, Approval↔CEO Decision. Full table in `CLAUDE.md`.
