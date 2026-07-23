"""Approvals module.

Owns the approval request/decision lifecycle for large decisions
(architecture changes, database schema, provider change, model change,
production deployment, external tool installation). Learns about approval
requests only via events on the Event Bus (published by workflow_engine),
never via a direct call — and publishes approval.granted / approval.rejected
once the CEO decides.

Allowed dependencies: event_bus.

No implementation yet (Sprint 1 defines module boundaries only).
"""
