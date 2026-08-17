"""Tasks module (Missions).

New in Sprint 3 — the Sprint 1/2 module list didn't assign an owner for
task CRUD (see docs/DECISIONS.md). Owns task entities and the assign
action, which transitions CREATED -> ASSIGNED and hands off to
workflow_engine.start_task to run the PM -> Engineer -> Reviewer pipeline.

`create_task`/`assign_task`/`TaskResponse` are re-exported here (Rule #1):
Sprint 12's `POST /specifications/{id}/begin-execution` converts an approved
Project Specification into a Mission through this same authoritative path
rather than duplicating task-creation/assignment logic, and returns the
resulting Mission through this same response contract -- importing them
through this package's public surface, not `.service`/`.schemas` directly,
keeps those modules a private implementation detail.
"""

from .routes import router
from .schemas import TaskResponse
from .service import assign_task, create_task, recover_orphaned_tasks

__all__ = ["router", "recover_orphaned_tasks", "create_task", "assign_task", "TaskResponse"]
