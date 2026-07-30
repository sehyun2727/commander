# Backend Module Communication Rules

> **HISTORICAL (Sprint 2).** 이 문서는 초기 모듈 경계 설계 기록이며 현재 구현과 일치하지 않는다.
> 현재의 진실의 원천은 `docs/ARCHITECTURE.md`다. 참고용 이력으로만 읽어라.

Status: Sprint 2. Governs `apps/api/app/modules/*` and `apps/api/app/core/*`.

## Rules (enforced by code review until tests exist)

1. **No circular dependencies.** `event_bus` depends on nothing but
   `core.events`. Every other module may depend on `event_bus`; it may
   never depend back on them.
2. **API Server never contains AI logic.** The (not-yet-built) API layer
   may only call `workflow_engine` (via the `WorkflowEngine` interface),
   plus the thin modules (`auth`, `projects`, `approvals`, `timeline`,
   `reports`, `model_registry`). It must never import `agent_runtime` or
   `provider_gateway` directly.
3. **Agents never call providers directly.** Only `provider_gateway` may
   call an AI provider SDK. `agent_runtime` must go through the
   `ProviderGateway` interface.
4. **Workspace changes always emit events.** Every mutating method on the
   `workspace_manager` implementation must publish a `workspace.*` event.
   ✅ Structurally enforced as of Sprint 2 — see
   `docs/backend/workflow/WORKSPACE_CONTRACT.md`.
5. **Timeline only consumes events.** `timeline` and `reports` subscribe to
   `event_bus`; neither has, nor needs, a publish path.
6. **Modules never import each other by concrete class** — only by the
   interfaces in `core.interfaces`. This is what makes every backbone
   module replaceable (Design Principle 5, "every model is replaceable",
   generalized to every backbone module).

## Layered dependency graph

Each layer may depend only on layers below it, plus `event_bus`. There is
no sideways or upward dependency.

`core.lifecycle` (agent/task states) and `core.errors` (named failure
types) sit alongside `core.events`: pure data, no dependencies of their
own, so every module may depend on them freely without risking a cycle.

```
Layer 0 — foundation
  event_bus                       -> core.events only

Layer 1 — domain engines (own data, no orchestration)
  workspace_manager                -> event_bus
  model_registry                    -> event_bus
  provider_gateway                  -> event_bus, model_registry

Layer 2 — orchestration
  agent_runtime                     -> event_bus, workspace_manager, provider_gateway
  workflow_engine                    -> event_bus, agent_runtime

Layer 3 — API-facing (thin, no AI logic)
  auth                               -> (none)
  projects                           -> event_bus
  approvals                          -> event_bus
  timeline                           -> event_bus (subscribe only)
  reports                            -> event_bus (subscribe only)

Entry point (not built this sprint)
  API routers -> workflow_engine, auth, projects, approvals, timeline,
                 reports, model_registry
```

`workflow_engine` and `approvals` never call each other directly —
`workflow_engine` publishes `approval.requested`; `approvals` subscribes to
it and later publishes `approval.granted` / `approval.rejected`. This keeps
the approval flow decoupled per Design Principle 7 ("Event Driven. Never
tightly coupled.").

## Resolved gap (was: Sprint 1 "Known gap")

Rule 4 used to be a documentation convention only. Sprint 2 made
`WorkspaceManager` a concrete base class whose public mutating methods
always publish an event around an abstract git-logic hook — verified by
instantiating a test implementation and confirming the event fires with
no way to skip it. Full writeup: `docs/backend/workflow/WORKSPACE_CONTRACT.md`.

## New gap (flagged Sprint 2, not fixed)

The `@final` decorators that make `WorkspaceManager`'s public methods
non-overridable are a static-analysis hint only — Python doesn't enforce
them at runtime. A type checker (mypy/pyright) needs to run in CI for this
to be a real guarantee. Suggested for Sprint 3.
