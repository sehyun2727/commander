"""Tasks module (Missions).

New in Sprint 3 — the Sprint 1/2 module list didn't assign an owner for
task CRUD (see docs/DECISIONS.md). Owns task entities and the assign
action, which transitions CREATED -> ASSIGNED and hands off to
workflow_engine.start_task to run the PM -> Engineer -> Reviewer pipeline.
"""

from .routes import router

__all__ = ["router"]
