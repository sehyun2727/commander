# PM Responsibility

Status: Sprint 2. The PM is an **agent role** dispatched by
`agent_runtime` (per `docs/ARCHITECTURE.md` § "Agent Runtime"), not its
own module — it has no dedicated code module, only a formalized set of
responsibilities mapped onto existing interfaces/events.

| Responsibility | Where it lives | How |
|---|---|---|
| Understand CEO natural language | `WorkflowEngine.handle_ceo_request(project_id, instruction)` | Entry point from the API layer; internally dispatches a `pm` agent (via `AgentRuntime.dispatch("pm", ...)`) to interpret the instruction. |
| Create tasks | `WorkflowEngine.create_work_item(project_id, title, priority)` | Called once per task the PM's interpretation produces. Publishes `TaskCreated`. |
| Prioritize work | `TaskCreated.priority` field (`low`/`normal`/`high`/`critical`) | The PM sets this at creation time; `assign_agent` / dispatch ordering should prefer higher priority when multiple idle agents are available. No scheduling algorithm is specified here — that's an implementation decision for whichever sprint builds `workflow_engine`. |
| Assign agents | `WorkflowEngine.assign_agent(task_id, agent_role)` | Chooses *which role* (Backend, Frontend, QA, Reviewer, ...); actual dispatch to a specific agent instance goes through `AgentRuntime.dispatch`. |
| Request approvals | `ApprovalRequested` event | Published when a task's next step is one of the "large decisions" in `docs/ARCHITECTURE.md` § "Approval Flow" (architecture change, DB schema, provider/model change, prod deployment, external tool install). The PM does not decide small vs. large itself in an ad-hoc way — that list is the fixed source of truth. |
| Summarize progress | Reports module + Timeline | `reports` mechanically compiles the daily report from historical events (no PM involvement needed). Whether the PM *additionally* posts narrative commentary to Timeline's "AI Discussion" thread type is an open question — see Risks below. |

## How the PM never violates "agents never communicate directly"

The PM agent does not call `create_work_item` itself (agents don't call
modules directly). The flow is:

1. `workflow_engine.handle_ceo_request` dispatches a planning task to the
   `pm` role via `AgentRuntime`.
2. The PM agent (running inside `agent_runtime`) produces a plan and,
   like every agent, can only communicate its result via an event.
3. `workflow_engine` — already subscribed to that event type — reacts by
   calling `create_work_item` / `assign_agent` for each proposed task.

This sprint does not add a dedicated "plan ready" event type, since no
implementation exists yet to produce or consume it; the next module-level
sprint that builds `workflow_engine`/`agent_runtime` should add it then
(flagged in Risks).

## Risks

- **Timeline content vs. Event Bus events aren't clearly the same thing.**
  `docs/ARCHITECTURE.md` says Timeline supports "Thread, Mentions, AI
  Discussion, CEO Messages" — these read as conversational artifacts, not
  system facts like `TaskCreated`. If PM "summarizing progress" means
  posting prose to Timeline, that may need its own contract distinct from
  `core.events` (which models facts, not conversation). Not resolved this
  sprint — flagged for whoever designs Timeline's data model.
