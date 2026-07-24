from __future__ import annotations

from app.core.contracts import AGENT_STATE_STATUS_WORD, TASK_STATE_STATUS_WORD, StatusWord
from app.core.lifecycle.agent_states import AgentState
from app.core.lifecycle.task_states import TaskState


def test_every_task_state_maps_to_a_status_word():
    assert set(TASK_STATE_STATUS_WORD.keys()) == set(TaskState)
    assert all(isinstance(v, StatusWord) for v in TASK_STATE_STATUS_WORD.values())


def test_every_agent_state_maps_to_a_status_word():
    assert set(AGENT_STATE_STATUS_WORD.keys()) == set(AgentState)
    assert all(isinstance(v, StatusWord) for v in AGENT_STATE_STATUS_WORD.values())


def test_pending_approval_maps_to_needs_decision():
    assert TASK_STATE_STATUS_WORD[TaskState.PENDING_APPROVAL] == StatusWord.NEEDS_DECISION
