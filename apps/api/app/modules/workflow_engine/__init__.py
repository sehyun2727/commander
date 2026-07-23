"""Workflow Engine module — the brain of Commander.

Will implement core.interfaces.workflow_engine.WorkflowEngine. Receives a
CEO instruction from the API layer, has the PM agent interpret it into
tasks, assigns tasks via Agent Runtime, and requests approvals for large
decisions. Contains no UI code.

Allowed dependencies: event_bus, agent_runtime (both via their interfaces
in core.interfaces — never a concrete implementation).

No implementation yet (Sprint 1 defines module boundaries only).
"""
