# Task Lifecycle

Status: Sprint 2. Implemented as `apps/api/app/core/lifecycle/task_states.py`
(`TaskState`, `TASK_TRANSITIONS`).

## Diagram

```
 ┌─────────┐  cancel   ┌───────────┐
 │ CREATED │──────────▶│ CANCELLED │◀────────────────────────┐
 └────┬────┘           └───────────┘                         │
      │ assign                                                │
      ▼                                                       │
 ┌──────────┐  cancel                                         │
 │ ASSIGNED │───────────────────────────────────────────────┐ │
 └────┬─────┘                                                │ │
      │ start                                                │ │
      ▼                                                       │ │
 ┌─────────────┐  fail            cancel                     │ │
 │ IN_PROGRESS │────────┐  ┌──────────────────────────────────┘ │
 └────┬────────┘        │  │                                    │
      │ submit           │  │                                    │
      ▼                  │  │                                    │
 ┌───────────┐  approved, no approval needed        ┌──────────┐│
 │ IN_REVIEW │─────────────────────────────────────▶│ COMPLETED││
 └─┬───┬───┬─┘                                       └──────────┘│
   │   │   │ approved, needs CEO sign-off                          │
   │   │   ▼                                                       │
   │   │ ┌──────────────────┐  approved        ┌──────────┐        │
   │   │ │ PENDING_APPROVAL │─────────────────▶│ COMPLETED│        │
   │   │ └───┬─────────┬────┘                  └──────────┘        │
   │   │     │ rejected │ rejected -> abandon                       │
   │   │     ▼          └──────────────────────────────────────────┘
   │   │  IN_PROGRESS (rework)
   │   │ rejected (rework loop)
   │   └──────────────▶ IN_PROGRESS
   │ rejected beyond rework limit
   ▼
 ┌────────┐  retries remain   ┌───────────┐  new attempt   ┌──────────┐
 │ FAILED │──────────────────▶│ RETRYING  │───────────────▶│ ASSIGNED │
 └───┬────┘                   └───────────┘                └──────────┘
     │ retries exhausted, CEO abandons
     ▼
 CANCELLED
```

## States

| State | Meaning |
|---|---|
| `CREATED` | Task exists (from `create_work_item`), not yet assigned. |
| `ASSIGNED` | An agent role has been chosen; work hasn't started. |
| `IN_PROGRESS` | Agent is actively executing (`TaskStarted` fired). |
| `IN_REVIEW` | Submitted to a Reviewer agent. |
| `PENDING_APPROVAL` | Review passed, but this is a "large decision" per the Approval Flow in `docs/ARCHITECTURE.md` (architecture change, DB schema, provider/model change, prod deployment, external tool install) and needs the CEO. |
| `COMPLETED` | Terminal — done. |
| `FAILED` | Execution could not succeed. Not always terminal — see retry below. |
| `RETRYING` | A transient failure occurred and a retry is authorized; about to re-enter `ASSIGNED`. |
| `CANCELLED` | Terminal — abandoned, by CEO or PM decision. |

## Transition rules

Defined exhaustively in `TASK_TRANSITIONS` and enforced the same way as
`AGENT_TRANSITIONS` — via `core.lifecycle.state_machine.transition()`.

- `CREATED → ASSIGNED | CANCELLED`
- `ASSIGNED → IN_PROGRESS | CANCELLED`
- `IN_PROGRESS → IN_REVIEW | FAILED | CANCELLED`
- `IN_REVIEW → PENDING_APPROVAL | COMPLETED | IN_PROGRESS (rework) | FAILED (rework limit exceeded)`
- `PENDING_APPROVAL → COMPLETED | IN_PROGRESS (rework) | CANCELLED`
- `FAILED → RETRYING | CANCELLED`
- `RETRYING → ASSIGNED`
- `COMPLETED`, `CANCELLED` are terminal (no outgoing transitions).

## Notes on the requested states

- **Retry** is modeled as its own transitional state (`RETRYING`) rather
  than an implicit loop, so a retry attempt is a distinct, observable
  moment (`TaskRetried` event, carrying `attempt`) — consistent with
  "everything is observable, nothing happens silently."
- **Cancellation** is reachable from every non-terminal state, matching
  that a CEO can call off work at any point.
- Whether a `FAILED` task moves to `RETRYING` or stays `FAILED` (awaiting
  CEO escalation) is a *policy* decision, not a lifecycle one — see
  FAILURE_HANDLING.md for the retry/escalation rules that decide it.

## Observability

Same pattern as agents: every transition should run through
`transition(..., on_transition=publish_task_state_changed)`, firing
`TaskStateChanged` on every change, while the curated events (`TaskAssigned`,
`TaskStarted`, `TaskCompleted`, `TaskFailed`, `TaskRetried`, `TaskCancelled`,
`ReviewStarted`/`Completed`, `ApprovalRequested`/`Granted`/`Rejected`) remain
what Timeline surfaces to the CEO.
