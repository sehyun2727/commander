# Decisions Log — Sprint 3 ("Make It Real")

Judgment calls made while building the vertical slice, in the order they
came up. Each one only exists because the brief left it open or because
existing Sprint 0-2 skeleton conflicted with the Sprint 3 spec (spec wins,
per the brief's constraints).

## Phase 1 — Contracts

1. **Event contracts moved from per-type frozen dataclasses to a single
   Pydantic v2 `Event` envelope with a JSON `payload`.** The Sprint 1/2
   skeleton had one dataclass subclass per event type with typed fields.
   Sprint 3's persistence decision is a single unified event-stream table,
   which means the DB column is JSON either way — keeping 30 dataclass
   subclasses added no type safety the DB round-trip couldn't already lose,
   and blocked easy TS codegen. Payload shape safety is preserved via
   `PAYLOAD_MODELS` (one Pydantic model per `EventType`) validated in
   `build_event()`.
2. **`kind` is inferred by `build_event()`** (`conversation` only for
   `conversation.message`, `system` otherwise) unless explicitly overridden
   — callers shouldn't have to repeat it for every system event.
3. **TS codegen is hand-rolled** (`scripts/generate_ts_schemas.py` walks
   `model_fields` directly) instead of using `pydantic2ts` or
   `datamodel-code-generator`. Both need either a Node subprocess or extra
   deps that aren't guaranteed to resolve offline; walking fields directly
   needed no new dependency and is ~120 lines.
4. Added `EventType.AGENT_CREATED`, `APPROVAL_CHANGES_REQUESTED`, and
   `SYSTEM_HEARTBEAT` — not in the original Sprint 1 enum but required by
   the Sprint 3 workflow (agent creation on company bootstrap, the CEO's
   third decision option, and SSE heartbeats).
5. Reused `AgentState`/`TaskState`/`AGENT_TRANSITIONS`/`TASK_TRANSITIONS`
   from Sprint 2 unchanged — they already match the Sprint 3 spec's agent
   lifecycle exactly.

(Further entries appended as later phases land.)
