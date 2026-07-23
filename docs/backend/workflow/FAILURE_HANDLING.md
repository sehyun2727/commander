# Failure Handling

Status: Sprint 2. Named failure types live in `apps/api/app/core/errors.py`.
No retry/escalation *logic* is implemented — this document is the policy
contract a future `workflow_engine` implementation must follow.

## Failure modes

| Scenario | Exception | Auto-retry? | Escalation |
|---|---|---|---|
| Task failed (agent reports unrecoverable error) | `CommanderError` (task-specific) | No — the agent already decided it can't proceed | `ApprovalRequested(subject="task_failure_escalation")` once retries (if any) are exhausted |
| Agent timeout | `AgentTimeoutError` | Yes, transient | Auto-retry first; escalate only if retries exhausted |
| Model unavailable | `ModelUnavailableError` | Yes, transient | Same as above — but see Recovery strategy: this should rarely surface at all |
| Workspace conflict | `WorkspaceConflictError` | **No** | Escalate immediately: `ApprovalRequested(subject="workspace_conflict")` |
| Review rejected | `ReviewRejectedError` | Not a failure — see below | Escalate only if rejected repeatedly (rework limit exceeded) |
| Approval rejected | `ApprovalRejectedError` | **No** | Terminal for that approach — PM must propose a different one (new task) or task is `CANCELLED` |

## Retry rules

- Default budget: 2 retries (3 attempts total) per task. Configurable per
  task type in a future sprint — not decided here.
- Only `AgentTimeoutError` and `ModelUnavailableError` are auto-retried
  without CEO involvement, because both are transient infrastructure
  problems, not decisions about the work itself.
- `WorkspaceConflictError` is **never** auto-retried: silently retrying a
  conflicting write risks overwriting someone's change. It always goes to
  the CEO.
- A review rejection is normal rework (`IN_REVIEW → IN_PROGRESS`), not a
  retry-budget failure — it only becomes an escalation if a task is
  rejected repeatedly beyond a rework limit (not yet numerically defined).

## Escalation rule

Every escalation reuses the existing Approval Flow from
`docs/ARCHITECTURE.md` (Approve / Reject / Discuss) rather than inventing
a parallel mechanism — this keeps every "someone needs to decide"
situation, whether it's a normal large decision or a failure, going
through the one place the CEO already looks.

## Recovery strategy

- **Agent-level**: `AgentRuntime.stop(agent_id)` then `dispatch()` a fresh
  instance of the same role. The stuck instance is discarded, not resumed.
  The task's retry `attempt` count is incremented (`TaskRetried`); the
  agent instance itself is irrelevant to that count.
- **Workspace conflict**: no automatic recovery is designed here —
  resolving which change wins is a human/PM decision, out of scope for
  this sprint (no Git implementation).
- **Model unavailable**: `ProviderGateway.complete()`'s contract implies
  the gateway should already have tried fallback models (per Model
  Registry's recommended ordering) *before* raising
  `ModelUnavailableError` — i.e., this error should be rare in practice.
  This is a documented expectation, not an interface change, since
  designing gateway fallback logic is provider implementation (out of
  scope this sprint).

## Not decided here

- Exact rework-rejection limit before a `ReviewRejectedError` escalates.
- Per-task-type retry budgets.
- Whether retries reuse the same branch/workspace state or start clean.

These are implementation decisions for the sprint that actually builds
`workflow_engine`.
