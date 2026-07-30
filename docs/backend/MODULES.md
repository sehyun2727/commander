# Backend Module Responsibilities

> **HISTORICAL (Sprint 2).** 이 문서는 초기 모듈 경계 설계 기록이며 현재 구현과 일치하지 않는다.
> 현재의 진실의 원천은 `docs/ARCHITECTURE.md`다. 참고용 이력으로만 읽어라.

Status: Sprint 2 — boundaries and contracts only, no implementation.
Source of truth: `../ARCHITECTURE.md`. This document must stay in sync with
`apps/api/app/modules/*/__init__.py`.

Every module below is a Python subpackage under `apps/api/app/modules/`.
Five of them ("backbone" modules) also have a matching interface under
`apps/api/app/core/interfaces/`, so their implementation can be swapped
without touching callers. The rest are thinner, API-facing modules with no
alternate implementation expected, so no interface was created for them —
see Sprint 0 architecture review if that assumption needs revisiting.

Alongside `core.events` (Sprint 1), `apps/api/app/core/` now also holds
`lifecycle/` (the `AgentState`/`TaskState` finite-state machines and the
shared `transition()` validator) and `errors.py` (the named
`CommanderError` hierarchy — see `docs/backend/workflow/FAILURE_HANDLING.md`).
Both are pure data/validation with no dependencies of their own, so every
module may depend on them freely — see `DEPENDENCIES.md`.

## Backbone modules (have an interface in core/interfaces)

### event_bus
Implements `EventBus`. Persists and dispatches every event in the system.
Depends on nothing but `core.events` — this is the dependency floor of the
backend, which is what makes "no circular dependencies" possible.

### workspace_manager
Implements `WorkspaceManager`. Owns the git repository: branches, diffs,
commits, file changes, patches, and human-readable summaries. As of Sprint 2
the interface itself is a concrete Template Method base class — `commit()`
and `create_branch()` are `@final` and unconditionally publish their
`workspace.*` event around an abstract `_do_*` git hook, so a subclass
structurally cannot mutate the workspace without publishing. See
`docs/backend/workflow/WORKSPACE_CONTRACT.md`.

### provider_gateway
Implements `ProviderGateway`. The only module allowed to call AI provider
APIs (OpenAI, Anthropic, Google, OpenRouter, future local models). Resolves
model → provider routing via `model_registry`. Expected to try fallback
models before raising `ModelUnavailableError` (see `FAILURE_HANDLING.md`).

### agent_runtime
Implements `AgentRuntime`. Hosts every running agent (PM, Backend Engineer,
Frontend Engineer, QA Engineer, Reviewer, ...). Agents never call each
other directly — only through events. Each agent's `AgentState` (see
`core.lifecycle`) is tracked here; `dispatch()` returns the new agent's id
and `get_state()` exposes its current lifecycle state.

### workflow_engine
Implements `WorkflowEngine`. The brain: receives a CEO instruction
(`handle_ceo_request`), has the PM agent interpret it, creates work items
and assigns agents via `agent_runtime`, monitors `TaskState` progress, and
routes failures (`handle_failure`) per `FAILURE_HANDLING.md`. Requests
approvals for large decisions by publishing events, not by calling
`approvals` directly. Contains no UI code.

## API-facing modules (no interface — no alternate implementation expected)

### auth
Authentication for the CEO Dashboard's single local user. Used only by the
API layer's request handling; no domain module depends on it and it
depends on none of them.

### projects
Owns project entities (create/list/archive). Other modules reference a
project only by `project_id` — never by importing this module.

### model_registry
Catalogs every available model per provider and which are "recommended".
Read by `provider_gateway` and by the API layer (Dashboard settings).

### approvals
Owns the approval request/decision lifecycle (architecture changes, DB
schema, provider change, model change, production deployment, external
tool installation). Learns about requests only via events published by
`workflow_engine` — never via a direct call.

### timeline
The CEO-facing company conversation feed — not chat, not logs. Consumes
events only; never publishes.

### reports
Compiles the CEO's daily report from historical events. Consumes events
only; never publishes, like `timeline`.

## Not yet a module

`docs/ARCHITECTURE.md` review (Sprint 0) flagged missing responsibilities —
a data/persistence layer, secrets manager, and execution sandbox — that
this sprint's module list does not include. They are out of scope here
because the Sprint 1 brief enumerates the module list explicitly; see the
Risks section of the Sprint 1 response for why they still need an owner
before real implementation starts.
