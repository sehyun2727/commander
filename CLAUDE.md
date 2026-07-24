# CLAUDE.md — Commander

Commander is an operating system where a solo developer becomes the **CEO of an AI software company**. AI agents work as Employees; the CEO instructs, observes, and decides. Sprint 3 shipped a working vertical slice: FastAPI backend + event bus + mock/Anthropic providers + SSE realtime + Next.js dashboard. Sprint 4 ("Real Intelligence") hardened the provider path (streaming, retries, real token usage) and added CEO-facing levers on top of it: Payroll, per-role model reassignment, and the Daily Report. Sprint 4.5 ("Employee Profiles") let the CEO customize each Employee's personality/working style/decision style and give per-Employee custom instructions and a model override, all flowing into the actual system prompt via `prompt_builder`.

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
apps/api/          FastAPI backend (Python 3.11+, async SQLAlchemy, SQLite)
  app/core/        events (schemas), interfaces (ports), lifecycle (state machines), db, secrets, config
  app/modules/     projects, tasks, approvals, timeline, agent_runtime, agent_profiles, prompt_builder,
                   workflow_engine, event_bus, provider_gateway, model_registry, costs, reports, realtime (SSE)
  tests/           pytest suite (56 tests)
apps/dashboard/    Next.js App Router + TS + Tailwind + TanStack Query (dark Render-style theme)
packages/event-schemas/ts/   generated TS event types — DO NOT hand-edit; regenerate
scripts/           generate_ts_schemas.py, seed.py
docs/              ARCHITECTURE.md (as-built), DECISIONS.md (judgment log), backend/ specs
docs/design/UX_SPEC.md   product experience source of truth — ALL frontend work follows it
docs/prompts/      sprint briefs
```

## Commands

```bash
make install   # api deps (pip -e) + dashboard deps (pnpm)
make seed      # reset DB, found demo company "Acme AI"
make dev       # api :8000 + dashboard :3000
make test      # pytest (apps/api)
python scripts/generate_ts_schemas.py   # after ANY event schema change
```

## Conventions

- Event contracts: single Pydantic v2 `Event` envelope + per-type payload models in `PAYLOAD_MODELS`, validated by `build_event()`. Adding an event type = enum entry + payload model + regenerate TS.
- State machines: `core/lifecycle/` owns Agent/Task states and legal transitions. Never mutate state fields directly — go through `transition()` so the change is validated and emitted.
- Each workflow step opens its own DB session; don't hold sessions across sleeps/awaits on the provider.
- Frontend: server data via TanStack Query; SSE events dedup by `event.id` and invalidate queries (`invalidateForEvent`). Generated types from `packages/event-schemas/ts` — never redeclare event shapes.
- Reviewer verdicts are parsed from a trailing `**Verdict:** ...` line — provider-agnostic; workflow never branches on provider.
- Commit style: `feat(scope): ...` / `fix(scope): ...` / `docs: ...` / `chore: ...`. Commit per meaningful unit.
- Every non-obvious judgment call gets one entry in `docs/DECISIONS.md`.

## Current Status (post-Sprint 4.5)

Working: company CRUD + auto-founded 3 Employees (PM/Engineer/Reviewer), Mission kanban, PM→Engineer→Reviewer pipeline with streaming replies and retry-with-backoff, CEO Decisions (approve / request changes / reject), unified Timeline + SSE live feed, Meeting chat, Company Settings with runtime API-key entry and per-role model reassignment, Payroll (real token usage → USD, company + per-Employee + per-Mission), on-demand CEO Daily Report (trailing-24h executive summary), seed/demo mode, Employee Profiles (CEO-editable personality/working-style/decision-style + up to 500-char custom instructions + per-Employee model override; three-tier model resolution is agent override > CEO per-role override > registry default; the Reviewer's role contract is appended last by `prompt_builder` and survives any custom instruction).

Not built yet (do NOT add without an explicit sprint brief): auth, execution sandbox, real code execution, Workspace Manager (git), cloud runner, deployment/Launch, multi-provider beyond Anthropic+mock.

Known accepted MVP tradeoffs: plaintext secrets in local SQLite, in-process event bus (single worker), inline subscriber execution in `publish`, Python-side conversation filtering, no DB migrations (`create_all` on boot). See `docs/DECISIONS.md` before "fixing" any of these.

## Working Style

- Work autonomously; when a brief leaves something open, make the reasonable call, log it in `docs/DECISIONS.md`, keep moving.
- Spec wins over legacy skeleton code — refactor, don't work around.
- Prefer boring, reliable choices. If a library fights you for >10 minutes, replace it.
- Self-verify before finishing: `make test`, `pnpm build` (dashboard), and boot the slice when behavior changed.
- Keep this file in sync: any architecture change must update CLAUDE.md and ARCHITECTURE.md in the same PR/commit. Desync is an architecture violation.
- Maintain PROGRESS.txt per the live progress discipline (see docs/prompts/) — update per item, never batched.