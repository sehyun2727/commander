"""Workflow Engine module — the brain of Commander.

Implements core.interfaces.workflow_engine.WorkflowEngine: runs the
PM -> Engineer -> Reviewer -> CEO Decision pipeline for a Mission as a
background asyncio task, publishing every step to the Event Bus. Depends
only on agent_runtime and provider_gateway via their core.interfaces ports.

`resolve_employee_for_role` is re-exported here (Rule #1): Sprint 12's
planning orchestrator needs the same Role -> Employee selection policy
this engine uses, and importing it through this package's public surface
-- rather than reaching into `.employee_resolution` directly -- keeps that
file a private implementation detail of this module.
"""

from .employee_resolution import resolve_employee_for_role
from .engine import CommanderWorkflowEngine

__all__ = ["CommanderWorkflowEngine", "resolve_employee_for_role"]
