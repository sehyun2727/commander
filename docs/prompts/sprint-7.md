# MISSION: Commander Sprint 7 — V1 Hardening & Dockerized Postgres

Read `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/design/UX_SPEC.md`, and `docs/DECISIONS.md` first — they are the source of truth for terminology, architecture rules, and current state. All architecture rules and the `PROGRESS.txt` discipline apply. Work autonomously start to finish; do NOT pause for confirmation between phases or items; log every judgment call in `docs/DECISIONS.md` under a new "Sprint 7" section. Commit AND PUSH per phase (a sprint is not complete until the remote HEAD matches the final commit — verify at the end).

Prerequisite: Sprint 6 merged (remote HEAD `6b5b9f8`), 142 passed / 4 skipped.

---

## Framing: this is a V1-completion sprint, not a feature sprint

Commander's roadmap is now explicitly two-phased: **finish V1 (Sprints 7–8), then build V1.5** (Agent Harness, CTO, PM Specification, Project Memory — all documented in `docs/V1.5-SPEC-refined.md`, and NONE of it is in scope here). V1 is the AI-organization prototype the CEO experiences end to end: found a company → assign a Mission → PM/Engineer/Reviewer collaborate (with real code deliverables and sandboxed checks, already built in Sprints 5–6) → CEO decides → completion report — all observable on the Timeline, all runnable against a real LLM.

Sprint 7 makes that prototype **production-runnable and trustworthy**: move persistence to a Dockerized Postgres, verify the real Anthropic path end to end (not just mock), harden the operational edges, and bring the docs/onboarding up to the actual shipped surface. NO new product capabilities. If you find yourself adding a feature, stop — that is scope creep; note it in DECISIONS.md as a V1.5 candidate and move on.

**Hard boundary — do NOT implement any of these (they are V1.5):** Agent Harness / iterative Engineer tool-loop, `read_file`/`write_file`/`run_checks` agent tools, CTO agent, PM structured Specification contract, Project Memory, requirement-change flow, EngineerWorker interface, ClaudeCodeWorker. The Engineer stays a single-shot generator exactly as it is today. You are hardening what exists, not evolving the workforce.

---

## Design decisions (approved — do not re-litigate)

- **Postgres in Docker is the new default datastore.** SQLite support stays wired (it's the zero-dependency fallback and keeps the existing test suite fast), but the documented, default `make dev` path runs against a Postgres 16 container. Selection stays via the single `settings.database_url` seam — no engine logic scattered elsewhere.
- **`docker-compose.yml` at repo root** owns the Postgres service (named volume for durability, healthcheck, port 5432, sensible dev credentials via `.env`). Reuse the same Docker dependency the Sprint 6 sandbox already assumes — do NOT add Postgres to the sandbox image or route DB traffic through the sandbox; they are independent Docker uses.
- **JSON columns**: SQLAlchemy's generic `JSON` type already maps to Postgres `JSONB`-compatible storage. Keep the generic type (portable across both engines); do NOT switch to the Postgres-specific dialect type — portability is the point.
- **Migrations**: introduce **Alembic** now (V1 ships to a persistent DB, so `create_all`-only is no longer acceptable). Generate one baseline migration matching the current models; `make db-upgrade` applies it; startup no longer blindly `create_all`s against Postgres. Keep `create_all` for the SQLite test path (fast, ephemeral) — gate on engine or on a test flag.
- **`make seed` must work against Postgres**: reset semantics = truncate/drop-and-recreate via the service layer, same demo "Acme AI" outcome as today.
- **Real-LLM verification is a first-class deliverable**, not a side note — Sprint 6 left real-Docker E2E pending; Sprint 7 must not leave real-LLM E2E pending. You have Docker locally and the environment can reach `api.anthropic.com`. If an `ANTHROPIC_API_KEY` is available, run a real end-to-end mission and record the result + observed cost in DECISIONS.md. If no key is available, make that the ONE explicitly-flagged carryover (mirror Sprint 6 #107) and provide a copy-paste script the CEO can run to verify in one command.
- **Secrets**: `.env` stays the mechanism via the existing `SecretsProvider`; add `.env.example` documenting every variable (`DATABASE_URL`, `COMMANDER_PROVIDER`, `ANTHROPIC_API_KEY`, sandbox image name, Postgres creds). Never commit real secrets; confirm `.gitignore` covers `.env` and `commander.db`.

---

## Phase 0 — Hygiene & audit (do first, small)

- Read the current `Makefile`, `apps/api/app/core/config.py`, `apps/api/app/core/db.py`, and `docker_sandbox.py` so your Docker and DB work is consistent with what exists.
- Confirm the CLAUDE.md push rule is present (it was scheduled for Sprint 6 Phase 0); if missing, add to Working Style: "Every sprint's final phase commit must be followed by `git push`; a sprint is not complete until the remote HEAD matches the final commit."
- Create `PROGRESS.txt` from Appendix A, all `[ ]`, before any other work; backfill Phase 0 items as you finish them.
- Commit+push: `chore(sprint7): phase 0 audit + progress scaffold`

## Phase 1 — Dockerized Postgres

- `docker-compose.yml`: `postgres:16` service, named volume, healthcheck, env-driven creds, `.env`/`.env.example`.
- `config.py`: default `database_url` reads from env; document that the compose Postgres URL is the intended default for `make dev`, SQLite the fallback for tests/quick local runs.
- `apps/api/pyproject` (or requirements): add `asyncpg` (async Postgres driver) and `alembic`.
- `db.py`: engine selection stays on the single URL seam; ensure async engine works with `postgresql+asyncpg`.
- Makefile: `make db-up` (compose up postgres + wait for healthy), `make db-down`, and wire `make dev` to ensure Postgres is up first. Keep every existing target working.
- Verify: containerized Postgres boots, the API connects, a manual smoke insert/read round-trips.
- Commit+push: `feat(db): dockerized postgres service`

## Phase 2 — Alembic migrations

- Initialize Alembic (async-compatible env.py) against the models in `apps/api/app/core/db_models.py`.
- Generate the **baseline migration** capturing the full current schema (projects, agents, tasks, events, approvals, reports, settings_kv, costs, and any Sprint 5–6 additions like code_stats/check_results/sections — audit the models, don't assume).
- `make db-upgrade` / `make db-downgrade`. Startup path: migrate on Postgres, `create_all` only for ephemeral SQLite tests.
- `make seed` works against Postgres (service-layer reset, same Acme AI result).
- Verify: fresh Postgres volume → `make db-upgrade` → `make seed` → API serves the seeded company with zero errors.
- Commit+push: `feat(db): alembic baseline migration`

## Phase 3 — Real LLM verification & provider hardening

- End-to-end against the real Anthropic provider (`COMMANDER_PROVIDER=anthropic`): found a company, run a code Mission through PM→Engineer→Reviewer→CEO Decision, confirm streaming, Payroll cost capture, and sandboxed checks all behave with real model output. Record outcome + observed cost in DECISIONS.md.
- Harden real-path edges surfaced by the run: missing/invalid API key → clear, CEO-legible error (never a stack trace in the UI); Anthropic 429/5xx already retried (Sprint 4) — confirm still true through the current pipeline; confirm the `**Verdict:**` and Problem/Recommendation/Risk/Impact parsing survives real (non-mock) Reviewer output (this is the highest-risk real-LLM item — mock output is clean, real output rambles; parsing must stay lenient and never break the pipeline).
- Provide `scripts/verify_real_llm.py` (or a `make verify-llm` target): one command that, given a key, runs the smoke mission and prints pass/fail — so the CEO can re-verify anytime.
- Commit+push: `feat(providers): real-LLM verification + edge hardening`

## Phase 4 — Operational hardening

- **Health & readiness**: `GET /api/health` (process up) and `/api/health/db` (DB reachable) — used by compose healthcheck and for the CEO's peace of mind.
- **Config validation on boot**: if `COMMANDER_PROVIDER=anthropic` but no key, or `DATABASE_URL` unreachable, fail fast with a plain-language message telling the CEO exactly what to fix — never a raw traceback.
- **Frontend resilience**: API-down and mid-stream SSE-drop states render a calm, Commander-voiced message ("Reconnecting to your company…"), not a blank screen or console error. Audit the existing SSE hook for reconnect behavior; add bounded reconnect if absent.
- **Data-safety pass**: confirm no destructive operation (drop, truncate, hard delete) can be triggered from the UI or a normal API call — only `make seed`/migration CLIs. This upholds the product's "history is never deleted" trust principle.
- Commit+push: `feat(ops): health checks, boot validation, resilient frontend`

## Phase 5 — Docs, onboarding & release readiness

- **README** rewrite: it currently says "Sprint 3." Bring it to the real V1 surface — what Commander is, the full quickstart (`make db-up && make db-upgrade && make seed && make dev`), mock-vs-real provider, the Docker prerequisites (Postgres + optional sandbox image), and a 6-step "your first company" walkthrough. This is a portfolio-facing document — make it clear and credible, no hype.
- **CLAUDE.md**: update Current Status to reflect Postgres/Alembic/health/real-LLM-verified; update the Repo Layout with docker-compose, alembic, new scripts; add a one-line "V1 vs V1.5 boundary" note pointing at `docs/V1.5-SPEC-refined.md` so no future session re-confuses the phases.
- **ARCHITECTURE.md**: datastore section (Postgres default + SQLite fallback + Alembic), health endpoints, updated "accepted tradeoffs" (drop the SQLite-only and no-migrations entries).
- **DECISIONS.md**: Sprint 7 section with every judgment call.
- Full verification: `make test` green (adjust only where the DB path legitimately changed; the SQLite test path must stay green and fast); `tsc --noEmit` + `next build` clean; the real-DB `make dev` boot works.
- Commit+push: `chore(sprint7): docs, onboarding, release readiness` — then confirm remote HEAD matches.

---

## Out of scope (V1.5 or later — do not build)

Everything in the "Hard boundary" list above; hosted/cloud deployment (that's Sprint 8's "Launch" surface, and even then only the in-product Launch flow, not real cloud infra); multi-user/auth; provider beyond Anthropic+mock; remote git hosting; horizontal scaling of the in-process event bus.

## Definition of Done

`docker compose up -d postgres` (or `make db-up`) → `make db-upgrade && make seed && make dev` → dashboard runs against Postgres with zero errors → found a company and run a Mission in **mock** mode (full pipeline, checks, decision, report) → switch to **real** Anthropic mode with a key and run one Mission successfully (or, if no key, `make verify-llm` is ready and the carryover is flagged) → API-down and SSE-drop states degrade gracefully → `make test` green, `next build` clean → README/CLAUDE.md/ARCHITECTURE.md/DECISIONS.md all reflect the true V1 surface → `PROGRESS.txt` 100% with honest timestamps → remote HEAD = final commit.

---

## Appendix A — PROGRESS.txt checklist (create verbatim, header included)

```
================================================
 COMMANDER — SPRINT PROGRESS
 Sprint: 7 — V1 Hardening & Dockerized Postgres
 Overall: 0/34 items · 0%
 Now working on: —
 Last update: (set on creation)
================================================

PHASE 0 — Hygiene & Audit                                      (0/4)
[ ] 0.1  Read Makefile / config.py / db.py / docker_sandbox.py
[ ] 0.2  Confirm/add CLAUDE.md push rule
[ ] 0.3  Create PROGRESS.txt
[ ] 0.4  Commit+push: chore(sprint7) phase 0

PHASE 1 — Dockerized Postgres                                  (0/7)
[ ] 1.1  docker-compose.yml (postgres:16, volume, healthcheck)
[ ] 1.2  .env + .env.example (all vars documented)
[ ] 1.3  config.py: env-driven database_url, Postgres default for make dev
[ ] 1.4  Add asyncpg + alembic deps
[ ] 1.5  db.py works with postgresql+asyncpg
[ ] 1.6  Makefile: db-up / db-down / dev ensures postgres
[ ] 1.7  Commit+push: feat(db) dockerized postgres

PHASE 2 — Alembic Migrations                                   (0/6)
[ ] 2.1  Alembic init (async env.py)
[ ] 2.2  Baseline migration (audit ALL models incl. Sprint 5-6 cols)
[ ] 2.3  make db-upgrade / db-downgrade
[ ] 2.4  Startup: migrate on PG, create_all only for SQLite tests
[ ] 2.5  make seed works on Postgres (fresh volume -> upgrade -> seed)
[ ] 2.6  Commit+push: feat(db) alembic baseline

PHASE 3 — Real LLM Verification                                (0/6)
[ ] 3.1  Real Anthropic E2E mission (or flagged carryover if no key)
[ ] 3.2  Verdict + P/R/R/I parsing survives real rambly output
[ ] 3.3  Missing/invalid key -> CEO-legible error, no traceback
[ ] 3.4  429/5xx retry still holds through full pipeline
[ ] 3.5  scripts/verify_real_llm.py + make verify-llm
[ ] 3.6  Commit+push: feat(providers) real-LLM verification
[ ] +    Record real-run cost/outcome in DECISIONS.md

PHASE 4 — Operational Hardening                                (0/5)
[ ] 4.1  /api/health + /api/health/db
[ ] 4.2  Boot config validation (fail fast, plain language)
[ ] 4.3  Frontend API-down + SSE-drop graceful states
[ ] 4.4  Data-safety: no destructive op from UI/normal API
[ ] 4.5  Commit+push: feat(ops) hardening

PHASE 5 — Docs & Release Readiness                             (0/6)
[ ] 5.1  README rewrite (real V1 surface, full quickstart, walkthrough)
[ ] 5.2  CLAUDE.md status + layout + V1/V1.5 boundary note
[ ] 5.3  ARCHITECTURE.md datastore/health/tradeoffs update
[ ] 5.4  DECISIONS.md Sprint 7 section
[ ] 5.5  make test green + next build clean + real-DB boot verified
[ ] 5.6  Commit+push: chore(sprint7) docs; confirm remote HEAD
================================================
```