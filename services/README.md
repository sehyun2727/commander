# services

Reserved for future extraction of backend modules — Workflow Engine, Agent Runtime, Event Bus,
Provider Gateway, Model Registry — into independently deployable services, if/when scaling
requires it (see Architecture Review, Sprint 0: "Agent Runtime is a single, unscoped runtime").

Currently these modules live inside `apps/api` as a modular monolith. Nothing is implemented here yet.
