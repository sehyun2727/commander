# Commander

Commander is an operating system where a solo developer becomes the **CEO of an AI software company**. You never manage prompts — you found a Company, it auto-staffs with three AI Employees (PM, Engineer, Reviewer), you hand it Missions, and every action they take is visible, explainable, and reviewable before it lands.

Status: **V1 released** (`v1.0.0`) — a real, working vertical slice. FastAPI backend, Postgres-backed persistence with Alembic migrations, an event-driven core, mock and real (Anthropic) providers, an SSE-realtime Next.js dashboard, a real git-backed Workspace per company, and a sandboxed execution gate for automated checks. **V1.1 is in development.** Sprint 9 (Phase A) shipped local CEO accounts + session auth on top of V1. Sprint 10 (Phase B) split Role (template-owned position) from Employee (company-owned instance). Sprint 11 added a hireable CTO position and a CEO-facing "Hire Employee" flow — the CEO can now hire multiple Employees per worker Role and configure each one's model and skill template independently. Sprint 12 added PM↔CTO planning: hand the PM a vague request and it discusses it with the CTO (bounded turns), asks the CEO to clarify anything it can't honestly answer itself, and produces a reviewable, versioned **Project Specification** — engineering never starts until the CEO approves it. Sprints 13–14 shipped the **CEO Workspace** (`/company/[id]`), a single server-derived view of what needs the CEO next. Sprint 15 made that Workspace's optional sections configurable per-Company widgets — reorder, hide, and restore them, with layout choices persisted per CEO. See `CLAUDE.md` §9 for the remaining roadmap (a conversation-first CEO Workspace, an Agent Harness, and Project Memory). Everything below describes what's runnable **today**.

---

## What it does

- **Sign in as CEO.** A local email+password account, an HttpOnly session cookie, and every Company scoped to its owner — another account's data returns a plain 404, not a hint that it exists.
- **Found a Company** and it auto-staffs three Employees: a PM, an Engineer, and a Reviewer, each with an editable personality/working-style/decision-style profile.
- **Hire a CTO**, then hand the PM a request instead of a fully-formed Mission. The PM and CTO discuss it (visible, bounded turns), ask you to clarify anything they can't honestly resolve themselves, and hand back a **Project Specification** — goals, requirements, acceptance criteria, risks, and an implementation plan — for you to approve, send back for revision, or reject. Approving is what creates the Mission.
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

Then open **http://localhost:3000**. Commander requires a CEO account — sign in with the seeded demo account (`ceo@commander.local` / `commander1234`, overridable via `COMMANDER_DEMO_EMAIL`/`COMMANDER_DEMO_PASSWORD`) or register your own. Once signed in you'll see "Acme AI", a seeded demo Company with its three Employees and a couple of Missions already in flight, run entirely against the mock provider (zero API keys, zero cost).

`make seed` and `make dev` both depend on `db-up` (starts/waits on the `docker-compose` Postgres service) and `db-upgrade` (runs Alembic migrations to head), so there's no separate database setup step — the two commands above are the entire quickstart.

To start from a truly empty Commander instead of the seeded demo, skip `make seed` and just run `make db-up db-upgrade`, then `make dev`, and found your first Company from the dashboard's landing page.

### A first walkthrough

1. Sign in (demo account above, or register a new one) — every page except `/login` and `/register` requires a session.
2. On `/`, found a Company — give it a name and, optionally, a sentence about what it should build. If you fill in the second field, Commander skips straight to a live starter Mission instead of an empty kanban.
3. Land on the CEO Workspace (`/company/[id]`) — a single server-derived view of what needs you next (approve a decision, hire a vacant leadership role, answer a question), plus current focus, pending attention, planning/mission status, organization headcount, and recent activity, responsive down to mobile. The optional sections are widgets you can reorder, hide, and restore via **Customize Workspace**, with your layout saved per Company.
4. Open **Missions**, create one (or use a one-click starter), and assign it. Watch the PM → Engineer → Reviewer pipeline run live — streaming replies, then (for code Missions) a real commit on a mission branch, then automated checks if the template has any that match, then a Reviewer verdict.
5. When it reaches **Decisions**, review the Change Summary and diff (never raw deliverable text), then Approve, Request changes, or Reject. Approving a code Mission merges its branch.
6. Browse the Company's actual codebase under **Workspace**, check **Payroll** for real token spend, and pull an on-demand **Daily Report** or **Situation Report** any time.

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
make export-users  # export all CEO accounts to CSV on stdout (bcrypt hashes only, never plaintext)
```

`python scripts/reset_password.py <email> <new-password>` resets a CEO's password from the shell (min 8 chars) — no make target, since it's an interactive admin action, not part of any workflow.

---

## Health checks

- `GET /api/health` — liveness only, no dependencies, always `200` once the process is up.
- `GET /api/health/db` — readiness: a real round-trip against the configured database, `200` or a clean `503` if the database is unreachable (e.g. Postgres is down).

The dashboard polls `/api/health` and shows a banner if the API is unreachable; the SSE connection has its own "Reconnecting…" indicator if the live event stream drops.

On boot, the API logs its git SHA and Alembic revision (current vs. head) — check this line first whenever behavior doesn't match what you expect from the code; it's usually a stale process, not a bug.

---

## Restarting the API cleanly

The API, the dashboard, and CORS are all pinned to one host/port pair: `http://localhost:8000` (API) and `http://localhost:3000` (dashboard) — `NEXT_PUBLIC_API_URL`, `CORS_ORIGINS`, the Makefile, and `.env.local.example` all agree on this. Do not point any of them at `127.0.0.1` instead of `localhost`; browsers treat these as different origins for credentialed requests, so mixing them silently breaks the session cookie and looks like a CORS bug.

A stray API process left running on an old port (or an old code/schema version) is the most common cause of confusing failures — a request that looks like a CORS error in the browser, or a route that behaves like an older Sprint's code. Before filing a bug, make sure only one API process is running:

```bash
# find anything still listening on 8000 (or an old port like 8001)
lsof -i :8000        # macOS/Linux
netstat -ano | findstr :8000   # Windows

# stop make dev / make demo with Ctrl-C, then confirm nothing is left:
pkill -f "uvicorn app.main:app"   # macOS/Linux, if a background process survived
```

Then restart with `make dev` (or `make demo`) and check the boot log for the git SHA + Alembic revision to confirm you're running what you think you're running.

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
  app/modules/     auth (local accounts, sessions), projects, tasks, approvals, timeline,
                   agent_runtime, agent_profiles, prompt_builder, workflow_engine, event_bus,
                   provider_gateway, model_registry, costs, reports, situation, realtime (SSE),
                   workspace_manager (git-backed company codebase),
                   sandbox (Docker-isolated execution of trusted, template-defined checks)
  alembic/         async migration environment; `alembic/versions/` holds the schema history
  tests/           pytest suite
apps/dashboard/    Next.js App Router + TS + Tailwind + TanStack Query (dark Render-style theme)
packages/event-schemas/ts/   generated TS event types — do not hand-edit; regenerate
scripts/           generate_ts_schemas.py, seed.py, verify_real_llm.py, export_users.py,
                   reset_password.py
docs/              ARCHITECTURE.md (as-built), DECISIONS.md (judgment log), backend/ specs
docs/design/UX_SPEC.md   product experience source of truth
docs/prompts/      sprint briefs
```

---

## Product terminology

The UI speaks Commander's own vocabulary; the code speaks conventional engineering terms. If you're reading code and UI side by side: Project↔Company, User↔CEO, Repository↔Workspace, Task↔Mission, Issue↔Risk, Chat↔Meeting, Agent↔Employee, Dashboard↔CEO Workspace, Log↔Timeline, Configuration↔Company Settings, Review↔Audit, Approval↔CEO Decision. Full table in `CLAUDE.md`.
