# Agent Lifecycle

Status: Sprint 2. Implemented as `apps/api/app/core/lifecycle/agent_states.py`
(`AgentState`, `AGENT_TRANSITIONS`).

## Diagram

```
        ┌──────┐
   ┌───▶│ IDLE │◀────────────────────────────┐
   │    └──┬───┘                             │
   │       │ assign                          │
   │       ▼                                 │
   │   ┌──────────┐                          │
   │   │ ASSIGNED │──fail (unavailable)──┐    │
   │   └────┬─────┘                      │    │
   │        │ begin planning              │    │
   │        ▼                             │    │
   │   ┌──────────┐                       │    │
   │   │ PLANNING │──blocked (needs info)─┤    │
   │   └────┬─────┘                       │    │
   │        │ plan ready                  │    │
   │        ▼                             ▼    │
   │   ┌─────────┐   blocked         ┌────────┐│
   │   │ WORKING │◀─────────────────▶│ BLOCKED││
   │   └────┬────┘   unblock         └───┬────┘│
   │        │ submit for review          │ fail (unrecoverable)
   │        ▼                            │      │
   │  ┌────────────────┐                 │      │
   │  │ WAITING_REVIEW │                 │      │
   │  └───┬───────┬────┘                 │      │
   │      │       │ changes requested    │      │
   │      │       └──────────────────────┼─▶ WORKING (loop)
   │      │ approved                     │
   │      ▼                              ▼
   │  ┌───────────┐                 ┌────────┐
   └──│ COMPLETED │                 │ FAILED │──┘
      └───────────┘                 └────────┘
         (both return to IDLE — agent instances are reused across tasks)
```

## States

| State | Meaning |
|---|---|
| `IDLE` | No task assigned; available for dispatch. |
| `ASSIGNED` | Task handed to this agent; not yet started. |
| `PLANNING` | Interpreting the task before doing work (all roles, not just PM — e.g. a Backend Engineer plans its approach before coding). |
| `WORKING` | Actively executing. |
| `WAITING_REVIEW` | Submitted work, waiting on a Reviewer agent. |
| `BLOCKED` | Cannot proceed without something external: CEO approval, a dependency, or a transient failure (see FAILURE_HANDLING.md). |
| `COMPLETED` | Task finished successfully. Terminal for this assignment. |
| `FAILED` | Task could not be completed. Terminal for this assignment. |

`COMPLETED` and `FAILED` both transition back to `IDLE` — an agent
*instance* is reused across tasks (per `AGENT_TRANSITIONS`); it is the
*task* that has a one-shot lifecycle (see TASK_LIFECYCLE.md), not the
agent host.

## Transition rules

Defined exhaustively in `AGENT_TRANSITIONS` (a `dict[AgentState, set[AgentState]]`)
and enforced by `core.lifecycle.state_machine.transition()`, which raises
`InvalidTransition` for anything not listed. There is no fallback "allow
if unsure" path — every transition an implementation performs must be one
of:

- `IDLE → ASSIGNED`
- `ASSIGNED → PLANNING | FAILED` (assignment itself can fail, e.g. agent unavailable)
- `PLANNING → WORKING | BLOCKED | FAILED`
- `WORKING → WAITING_REVIEW | BLOCKED | FAILED`
- `WAITING_REVIEW → WORKING | COMPLETED | BLOCKED`
- `BLOCKED → PLANNING | WORKING | FAILED`
- `COMPLETED → IDLE`
- `FAILED → IDLE`

## Observability

Every transition should be run through `transition(..., on_transition=publish_agent_state_changed)`
so an `AgentStateChanged` event (see `core/events/contracts.py`) fires on
every state change — this is the low-level completeness net; `AgentStarted`
/ `AgentStopped` remain the curated, Timeline-facing events for the CEO
narrative (see EVENT_OWNERSHIP.md's note on granularity).
