"""Approvals module (CEO Decisions).

Owns the approval request/decision lifecycle. Learns about a request only
via the ApprovalRequested event published by workflow_engine — never via a
direct call. Deciding delegates to workflow_engine.resume_after_decision.
"""

from .routes import router

__all__ = ["router"]
