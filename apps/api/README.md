# API Server

FastAPI backend. Per `docs/ARCHITECTURE.md`, this service owns:

- Authentication
- Projects
- Agents
- Tasks
- Timeline
- Approvals
- Reports
- Provider Configuration

No AI logic exists here — AI calls are routed through the Provider Gateway module.

Internal modules are a modular monolith (confirmed Sprint 1), not standalone
deployables, until scaling requires extraction (see `../../services/README.md`).

## Structure

```
app/
├── core/
│   ├── events/         # Event contracts: Event, EventType, EventLike, per-domain events
│   └── interfaces/     # Replaceable-implementation ports:
│                       #   EventBus, WorkspaceManager, ProviderGateway,
│                       #   AgentRuntime, WorkflowEngine
└── modules/
    ├── auth/
    ├── projects/
    ├── workflow_engine/    # implements core.interfaces.WorkflowEngine
    ├── event_bus/          # implements core.interfaces.EventBus
    ├── agent_runtime/      # implements core.interfaces.AgentRuntime
    ├── workspace_manager/  # implements core.interfaces.WorkspaceManager
    ├── provider_gateway/   # implements core.interfaces.ProviderGateway
    ├── model_registry/
    ├── approvals/
    ├── timeline/
    └── reports/
```

See `../../docs/backend/MODULES.md` for what each module is responsible for
and `../../docs/backend/DEPENDENCIES.md` for which modules may depend on
which.

Status: contracts and module boundaries only (Sprint 1) — no routes, no
concrete implementations, no dependencies installed yet.
