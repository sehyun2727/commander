# Workspace Contract (Sprint 1 gap, resolved)

## The problem (Sprint 1)

`docs/backend/DEPENDENCIES.md` rule 4 says every workspace mutation must
emit an event. Sprint 1 shipped `WorkspaceManager` as a pure `ABC` —
nothing stopped a future implementation from committing without
publishing `WorkspaceCommitted`. The rule was convention, not code.

## The fix (Sprint 2)

`apps/api/app/core/interfaces/workspace_manager.py` changed from a pure
interface to a **concrete base class with a template method per mutation**:

- `create_branch()` and `commit()` are `@final` concrete methods. They
  call an abstract `_do_*` hook for the actual git logic, then
  unconditionally publish the corresponding event, then return.
- A concrete implementation (e.g. a future `GitWorkspaceManager`) only
  ever implements `_do_create_branch`, `_do_commit`, `_do_diff`,
  `_do_summarize` — it never touches the public methods, so it has no
  code path that mutates the workspace without also publishing an event.
- Read-only operations (`diff`, `summarize`) stay plain pass-throughs —
  they don't mutate anything, so no event is owed.

This was verified directly: a test implementation supplying only the
`_do_*` git hooks was instantiated, its `.commit()` called, and exactly
one `WorkspaceCommitted` event was published — with no way for the
subclass to have skipped it.

## Why this isn't "business logic" or "Git implementation"

The base class contains no git logic (the `_do_*` hooks remain abstract,
unimplemented) and no decisions (no branching on data, no retry, no
conflict resolution) — it only sequences "call hook → publish fixed event
→ return". This is orchestration plumbing, the same category as an ABC
itself, not domain logic. Flagging this explicitly since it's a real
shift from Sprint 1's "pure interface" pattern for this one module —
happy to revisit if this reasoning doesn't hold up on review.

## Remaining gap

`@final` (from `typing`) is a **static-analysis hint**, not a runtime
guard — Python will not stop a subclass from overriding `commit()` itself
at runtime. Enforcement requires a type checker (mypy/pyright) running in
CI. That's a tooling addition, not an architecture decision, so it's
deferred as a Sprint 3 suggestion rather than done here.
