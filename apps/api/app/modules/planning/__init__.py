"""Planning module (Sprint 12): PM<->CTO planning orchestration and the
Project Specification lifecycle -- start/resume/revise/cancel through
`PlanningOrchestrator`, and the CEO-decision endpoints
(approve/reject/begin-execution) that end a Specification's non-terminal
lifetime, all behind this package's public surface per Rule #1.
"""

from .routes import router

__all__ = ["router"]
