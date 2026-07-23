from __future__ import annotations

import pytest

from app.core.lifecycle.agent_states import AGENT_TRANSITIONS, AgentState
from app.core.lifecycle.state_machine import InvalidTransition, transition
from app.core.lifecycle.task_states import TASK_TRANSITIONS, TaskState


def test_task_created_to_assigned_is_allowed():
    assert transition(TaskState.CREATED, TaskState.ASSIGNED, TASK_TRANSITIONS) == TaskState.ASSIGNED


def test_task_completed_is_terminal():
    with pytest.raises(InvalidTransition):
        transition(TaskState.COMPLETED, TaskState.IN_PROGRESS, TASK_TRANSITIONS)


def test_task_cannot_skip_straight_to_completed_from_created():
    with pytest.raises(InvalidTransition):
        transition(TaskState.CREATED, TaskState.COMPLETED, TASK_TRANSITIONS)


def test_task_pending_approval_can_reject_back_to_in_progress():
    assert (
        transition(TaskState.PENDING_APPROVAL, TaskState.IN_PROGRESS, TASK_TRANSITIONS)
        == TaskState.IN_PROGRESS
    )


def test_agent_idle_to_assigned_is_allowed():
    assert transition(AgentState.IDLE, AgentState.ASSIGNED, AGENT_TRANSITIONS) == AgentState.ASSIGNED


def test_agent_cannot_go_idle_to_working_directly():
    with pytest.raises(InvalidTransition):
        transition(AgentState.IDLE, AgentState.WORKING, AGENT_TRANSITIONS)


def test_agent_completed_returns_to_idle():
    assert transition(AgentState.COMPLETED, AgentState.IDLE, AGENT_TRANSITIONS) == AgentState.IDLE


def test_on_transition_hook_only_fires_on_success():
    calls = []
    transition(AgentState.IDLE, AgentState.ASSIGNED, AGENT_TRANSITIONS, on_transition=lambda c, t: calls.append((c, t)))
    assert calls == [(AgentState.IDLE, AgentState.ASSIGNED)]

    with pytest.raises(InvalidTransition):
        transition(AgentState.IDLE, AgentState.WORKING, AGENT_TRANSITIONS, on_transition=lambda c, t: calls.append((c, t)))
    assert len(calls) == 1
