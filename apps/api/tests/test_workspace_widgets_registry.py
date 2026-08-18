"""Sprint 15 Phase 1 §11: canonical, typed, immutable Workspace widget
registry -- the same shape of guarantee `test_skill_templates.py` already
covers for skill templates."""

from __future__ import annotations

import dataclasses

import pytest

from app.modules.workspace_widgets.registry import (
    PRIMARY_NEXT_ACTION,
    REQUIRED_WIDGET_KEYS,
    WIDGETS,
    WIDGETS_BY_KEY,
)


def test_widget_definition_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        PRIMARY_NEXT_ACTION.title = "Something Else"  # type: ignore[misc]


def test_widgets_registry_is_the_only_source():
    assert set(WIDGETS_BY_KEY.keys()) == {w.key for w in WIDGETS}
    assert len(WIDGETS) == len(set(w.key for w in WIDGETS))  # no duplicate keys


def test_required_widgets_are_primary_action_and_connection_status():
    assert REQUIRED_WIDGET_KEYS == {"primary_next_action", "connection_status"}


def test_every_widget_has_a_legal_span():
    for widget in WIDGETS:
        assert widget.default_span in ("full", "half")


def test_default_orders_are_unique_and_dense():
    orders = sorted(w.default_order for w in WIDGETS)
    assert orders == list(range(len(WIDGETS)))
