from __future__ import annotations

import pytest

from app.modules.projects.service import create_project
from app.templates import TEMPLATE


@pytest.mark.asyncio
async def test_founding_posts_an_intro_conversation_event_per_employee(harness):
    """Sprint 4.7 §6: each Employee introduces themself in the Timeline
    right after founding, using the template's own intro line."""
    project = await create_project(harness.session_factory, harness.event_bus, harness.agent_runtime, "Acme", "mock", owner_id=harness.user.id)

    events, _ = await harness.event_bus.page(project.id, cursor=None, limit=50, kind="conversation")
    intro_texts = {event.payload["text"] for event in events}

    assert intro_texts == {role.intro for role in TEMPLATE.roles if role.founding}
    for event in events:
        assert event.kind == "conversation"
        assert event.payload["task_id"] is None
        assert event.payload["agent_id"] is not None


def test_starters_are_well_formed():
    assert len(TEMPLATE.starters) >= 1
    for starter in TEMPLATE.starters:
        assert starter["title"].strip()
        assert starter["description"].strip()
