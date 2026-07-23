"""Workflow Engine module — the brain of Commander.

Implements core.interfaces.workflow_engine.WorkflowEngine: runs the
PM -> Engineer -> Reviewer -> CEO Decision pipeline for a Mission as a
background asyncio task, publishing every step to the Event Bus. Depends
only on agent_runtime and provider_gateway via their core.interfaces ports.
"""

from .engine import CommanderWorkflowEngine

__all__ = ["CommanderWorkflowEngine"]
