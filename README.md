# Commander

Commander is an operating system where a solo developer becomes the CEO of an AI software company. Users manage a company, not prompts. Every AI action must be visible, explainable, reviewable, and replaceable.

Status: **Sprint 0 — architecture review & repository skeleton.** No application logic has been implemented yet.

## Source of truth

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — approved architecture (frozen pending CEO/CTO sign-off)
- `CLAUDE.md` — generated from the architecture once frozen; currently empty

## Repository layout

```
apps/        Frontend (dashboard) and backend (api) applications
packages/    Shared code used by multiple apps (schemas, ui, sdk, config)
services/    Reserved for backend modules if/when they're extracted into standalone services
plugins/     Reserved for the future plugin marketplace
runtime/     Reserved for the future local desktop runtime wrapper
docs/        Architecture docs and architecture decision records (ADRs)
```

See each subdirectory's `README.md` for its intended responsibilities.

## Development

Package management and dependency installation have not been set up yet — this repository currently contains configuration and structure only, no installable code.
