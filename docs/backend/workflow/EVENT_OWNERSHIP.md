# Event Ownership Decision

## Decision

**`apps/api/app/core/events` (Python) is the single source of truth** for
every event contract. `packages/event-schemas` (TypeScript) is a
*generated* artifact once codegen exists — never hand-maintained.

## Why Python, not TypeScript

- Every event originates server-side: agents, the workflow engine, and
  the workspace manager all run in the Python backend. The frontend only
  ever *consumes* events (Timeline rendering, WebSocket pushes) — it
  never produces one.
- Python's side is already fully built out (Sprint 1: `Event`, `EventType`,
  `EventLike`, 20+ concrete contracts; Sprint 2: 5 more). The TypeScript
  package is still an empty placeholder. Making the built side canonical
  avoids maintaining two hand-written copies that will drift the moment
  someone adds a field to one and forgets the other.

## Synchronization strategy (documented now, not built this sprint)

Building the generator is implementation work, out of scope for an
architecture sprint. The recommended approach for whichever sprint picks
this up:

1. Generate a language-neutral schema (JSON Schema) from the Python
   dataclasses in `core/events/contracts.py` — e.g. via a small
   introspection script, or by adopting `pydantic` models instead of
   plain dataclasses if runtime validation becomes useful anyway.
2. Generate TypeScript types for `packages/event-schemas` from that JSON
   Schema (`json-schema-to-typescript` or `quicktype` are common choices;
   not a commitment, just candidates).
3. Run the generator in CI and fail the build if `packages/event-schemas`
   is out of sync with the generated output — this is what actually
   prevents drift, not the choice of tool.
4. Until this exists, `packages/event-schemas/README.md` already carries
   a note pointing here so nobody starts hand-writing TS event types.

## What this does *not* decide

- Whether to adopt `pydantic` (validation library) is left open —
  noted as an option, not a decision, since it has broader implications
  (e.g. becomes a real dependency, not just stdlib dataclasses) beyond
  event ownership.
- The actual generator script, CI wiring, and JSON Schema shape are
  implementation, deferred to a future sprint.
