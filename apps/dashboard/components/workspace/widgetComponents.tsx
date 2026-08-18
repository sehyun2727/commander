import type { ComponentType } from "react";
import type { WorkspaceSnapshot } from "@/lib/types";
import { ConnectionStatusBar } from "@/components/workspace/ConnectionStatusBar";
import { CurrentFocusCard } from "@/components/workspace/CurrentFocusCard";
import { MissionSummaryCard } from "@/components/workspace/MissionSummaryCard";
import { OrganizationSummaryCard } from "@/components/workspace/OrganizationSummaryCard";
import { PendingAttentionList } from "@/components/workspace/PendingAttentionList";
import { PlanningSummaryCard } from "@/components/workspace/PlanningSummaryCard";
import { PrimaryActionPanel } from "@/components/workspace/PrimaryActionPanel";
import { RecentActivityList } from "@/components/workspace/RecentActivityList";

export interface WidgetRenderProps {
  snapshot: WorkspaceSnapshot;
  companyId: string;
  onRefresh: () => void;
}

// Sprint 15 §7.1/§8: the ONLY place a `widget_key` string is ever turned
// into a rendered component. This is a static, first-party, compile-time
// literal map -- never a dynamic import, never a lookup keyed by a
// client-provided module path. A widget_key with no entry here is
// "unsupported" and must degrade safely (page.tsx/WorkspaceWidgetGrid),
// never crash and never be treated as executable.
export const WORKSPACE_WIDGET_COMPONENTS: Record<string, ComponentType<WidgetRenderProps>> = {
  primary_next_action: ({ snapshot, companyId, onRefresh }) => (
    <PrimaryActionPanel nextAction={snapshot.next_action} companyId={companyId} onRefresh={onRefresh} />
  ),
  connection_status: () => <ConnectionStatusBar />,
  current_focus: ({ snapshot, companyId }) => <CurrentFocusCard focus={snapshot.focus} companyId={companyId} />,
  pending_attention: ({ snapshot, companyId }) => (
    <PendingAttentionList pending={snapshot.pending_actions} companyId={companyId} />
  ),
  planning_summary: ({ snapshot, companyId }) => (
    <PlanningSummaryCard planning={snapshot.planning} companyId={companyId} />
  ),
  missions_summary: ({ snapshot, companyId }) => (
    <MissionSummaryCard missions={snapshot.missions} companyId={companyId} />
  ),
  organization_summary: ({ snapshot, companyId }) => (
    <OrganizationSummaryCard organization={snapshot.organization} companyId={companyId} />
  ),
  recent_activity: ({ snapshot }) => <RecentActivityList items={snapshot.recent_activity} />,
};
