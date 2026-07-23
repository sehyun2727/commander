"""Generic transition-table validator, shared by AgentState and TaskState.

Pure validation — no persistence, no side effects of its own. The optional
`on_transition` hook exists so a future implementation can guarantee a
*StateChanged event is published on every state change, the same way
core.interfaces.workspace_manager.WorkspaceManager guarantees workspace.*
events: by making emission part of the one function that performs the
transition, not a separate step someone can forget.
"""

from __future__ import annotations

from typing import Callable, TypeVar

S = TypeVar("S")


class InvalidTransition(Exception):
    """Raised when a state change is not present in the transition table."""


def transition(
    current: S,
    target: S,
    table: dict[S, set[S]],
    on_transition: Callable[[S, S], None] | None = None,
) -> S:
    """Validate current -> target against table, then return target.

    Raises InvalidTransition if the move isn't allowed. If on_transition is
    given, it's called with (current, target) after validation succeeds —
    e.g. to publish TaskStateChanged / AgentStateChanged.
    """
    allowed = table.get(current, set())
    if target not in allowed:
        raise InvalidTransition(f"{current!r} -> {target!r} is not an allowed transition")
    if on_transition is not None:
        on_transition(current, target)
    return target
