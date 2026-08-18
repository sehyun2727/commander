"""Canonical, server-owned catalog of CEO Workspace widgets (Sprint 15
§4/§5, DECISIONS.md #228).

Same shape as `skill_templates/registry.py` (Sprint 11): a frozen dataclass
tuple plus a `WIDGETS_BY_KEY` lookup, immutable, zero per-project state --
every company sees the same catalog. This is the *only* allowlist of valid
widget keys; nothing else (client input, preference rows, normalization)
may invent a key that is not in `WIDGETS_BY_KEY`.

Each key maps 1:1 onto an existing `components/workspace/*` component
already shipped in Sprint 14 -- this module does not introduce new
Workspace content, only makes the existing composition configurable.
`required=True` widgets (the primary next action and the connection/
freshness indicator) can never be hidden and are always present in a
normalized preference set (§4.3: "the default layout must always provide
a useful Workspace").
"""

from __future__ import annotations

from dataclasses import dataclass

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class WidgetDefinition:
    key: str
    title: str
    description: str
    category: str
    required: bool
    default_visible: bool
    default_order: int
    # "full" spans the whole row; "half" packs two per row on desktop.
    # Mobile always renders a single column regardless of span (§4.9).
    default_span: str


PRIMARY_NEXT_ACTION = WidgetDefinition(
    key="primary_next_action",
    title="Primary Next Action",
    description="The one action the CEO should take next, server-derived and ranked.",
    category="action",
    required=True,
    default_visible=True,
    default_order=0,
    default_span="full",
)

CONNECTION_STATUS = WidgetDefinition(
    key="connection_status",
    title="Connection Status",
    description="Live-connection and data-freshness indicator for this Workspace.",
    category="status",
    required=True,
    default_visible=True,
    default_order=1,
    default_span="full",
)

CURRENT_FOCUS = WidgetDefinition(
    key="current_focus",
    title="Current Focus",
    description="The resource the organization is currently focused on.",
    category="status",
    required=False,
    default_visible=True,
    default_order=2,
    default_span="half",
)

PENDING_ATTENTION = WidgetDefinition(
    key="pending_attention",
    title="Pending CEO Attention",
    description="Clarifications, reviews, approvals, and failures waiting on the CEO.",
    category="action",
    required=False,
    default_visible=True,
    default_order=3,
    default_span="half",
)

PLANNING_SUMMARY = WidgetDefinition(
    key="planning_summary",
    title="Planning",
    description="Status of the current Project Specification, if any.",
    category="planning",
    required=False,
    default_visible=True,
    default_order=4,
    default_span="half",
)

MISSIONS_SUMMARY = WidgetDefinition(
    key="missions_summary",
    title="Missions",
    description="Active and recently updated Missions.",
    category="execution",
    required=False,
    default_visible=True,
    default_order=5,
    default_span="half",
)

ORGANIZATION_SUMMARY = WidgetDefinition(
    key="organization_summary",
    title="Organization",
    description="Leadership roster and Employee headcount/state breakdown.",
    category="organization",
    required=False,
    default_visible=True,
    default_order=6,
    default_span="half",
)

RECENT_ACTIVITY = WidgetDefinition(
    key="recent_activity",
    title="Recent Activity",
    description="The most recent Timeline events for this company.",
    category="activity",
    required=False,
    default_visible=True,
    default_order=7,
    default_span="half",
)

WIDGETS: tuple[WidgetDefinition, ...] = (
    PRIMARY_NEXT_ACTION,
    CONNECTION_STATUS,
    CURRENT_FOCUS,
    PENDING_ATTENTION,
    PLANNING_SUMMARY,
    MISSIONS_SUMMARY,
    ORGANIZATION_SUMMARY,
    RECENT_ACTIVITY,
)
WIDGETS_BY_KEY: dict[str, WidgetDefinition] = {widget.key: widget for widget in WIDGETS}
REQUIRED_WIDGET_KEYS: frozenset[str] = frozenset(w.key for w in WIDGETS if w.required)

MAX_WIDGET_ENTRIES = len(WIDGETS)
