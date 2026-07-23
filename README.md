# Commander

Commander is an operating system where a solo developer becomes the CEO of an AI software company. Users manage a company, not prompts. Every AI action must be visible, explainable, reviewable, and replaceable.

Status: **Sprint 3 — working vertical slice.** Persistence, an event-driven Department of Employees (PM/Engineer/Reviewer), a mock AI provider (no API key needed), realtime updates, and a Headquarters dashboard all run locally end to end.

## Quickstart

```bash
make install   # once: creates the API venv, installs deps (pnpm + pip)
make seed      # resets the dev DB and founds a demo company, "Acme AI"
make dev       # runs the API (:8000) and dashboard (:3000)
```

Open http://localhost:3000, pick **Acme AI**, create a Mission, and watch the Department work.

## Source of truth

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — approved architecture
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — judgment calls made while building the vertical slice

## Repository layout

```
apps/        Frontend (dashboard) and backend (api) applications
packages/    Shared code used by multiple apps (schemas, ui, sdk, config)
services/    Reserved for backend modules if/when they're extracted into standalone services
plugins/     Reserved for the future plugin marketplace
runtime/     Reserved for the future local desktop runtime wrapper
scripts/     Dev scripts (seed.py, TS schema codegen)
docs/        Architecture docs and architecture decision records (ADRs)
```

See each subdirectory's `README.md` for its intended responsibilities.

## Tests

`make test` runs the API's pytest suite plus the dashboard's typecheck and production build.
