# event-schemas

Canonical definitions for every event that flows through the Event Bus (see `docs/ARCHITECTURE.md`
§ "Event Bus"), e.g. `TaskCreated`, `TaskAssigned`, `CodingStarted`, `ReviewStarted`, `BugFound`,
`ApprovalRequested`, `DeploymentStarted`, `DeploymentCompleted`.

Intended to be the single source of truth consumed by both `apps/dashboard` (TypeScript) and
`apps/api` (Python), so event shapes never drift between frontend and backend.

Status: skeleton only — no TypeScript schemas defined yet.

**Decision (Sprint 2):** `apps/api/app/core/events` (Python) is the single
source of truth. This package will hold *generated* types once a
generator exists — never hand-written event definitions. See
`../../docs/backend/workflow/EVENT_OWNERSHIP.md` for the full rationale
and the synchronization strategy.
