"use client";

import { ErrorState } from "@/components/ErrorState";
import { ConnectionStatusBar } from "@/components/workspace/ConnectionStatusBar";
import { CurrentFocusCard } from "@/components/workspace/CurrentFocusCard";
import { MissionSummaryCard } from "@/components/workspace/MissionSummaryCard";
import { OrganizationSummaryCard } from "@/components/workspace/OrganizationSummaryCard";
import { PendingAttentionList } from "@/components/workspace/PendingAttentionList";
import { PlanningSummaryCard } from "@/components/workspace/PlanningSummaryCard";
import { PrimaryActionPanel } from "@/components/workspace/PrimaryActionPanel";
import { RecentActivityList } from "@/components/workspace/RecentActivityList";
import { useWorkspaceOverview } from "@/lib/hooks";

function WorkspaceSkeleton() {
  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:px-8 sm:py-10">
      <div className="mb-6 h-8 w-64 animate-pulse rounded bg-base-hover" />
      <div className="mb-6 h-28 animate-pulse rounded-xl bg-base-hover" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="h-40 animate-pulse rounded-xl bg-base-hover" />
        <div className="h-40 animate-pulse rounded-xl bg-base-hover" />
      </div>
    </main>
  );
}

// Sprint 14: the real CEO Workspace, replacing the previous Headquarters
// page as the company landing destination (§4.1, DECISIONS.md #223). Every
// value here comes straight from the Sprint 13 WorkspaceSnapshot contract
// -- this page never recomputes next_action's precedence, only renders it.
export default function WorkspacePage({ params }: { params: { id: string } }) {
  const companyId = params.id;
  const { data: snapshot, isLoading, isError, refetch } = useWorkspaceOverview(companyId);

  if (isLoading) {
    return <WorkspaceSkeleton />;
  }

  if (isError || !snapshot) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-8 sm:py-10">
        <header className="mb-6">
          <h1 className="text-2xl font-semibold text-text">CEO Workspace</h1>
        </header>
        <ErrorState description="Couldn't load the CEO Workspace. Try refreshing in a moment." />
      </main>
    );
  }

  const { project, organization, focus, pending_actions, next_action, planning, missions, recent_activity } = snapshot;

  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:px-8 sm:py-10">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold text-text">{project.name}</h1>
          <p className="mt-1 text-sm text-text-muted">CEO Workspace — everything that needs you, in one place.</p>
        </div>
        <ConnectionStatusBar />
      </header>

      <div className="mb-6">
        <PrimaryActionPanel nextAction={next_action} companyId={companyId} onRefresh={() => refetch()} />
      </div>

      {/* Mobile: single-column priority stack (§5). */}
      <div className="grid grid-cols-1 gap-4 lg:hidden">
        <PendingAttentionList pending={pending_actions} companyId={companyId} />
        <CurrentFocusCard focus={focus} companyId={companyId} />
        <PlanningSummaryCard planning={planning} companyId={companyId} />
        <MissionSummaryCard missions={missions} companyId={companyId} />
        <OrganizationSummaryCard organization={organization} companyId={companyId} />
        <RecentActivityList items={recent_activity} />
      </div>

      {/* Desktop: grouped two-column rows (§5). */}
      <div className="hidden lg:block">
        <div className="grid grid-cols-2 gap-4">
          <CurrentFocusCard focus={focus} companyId={companyId} />
          <PendingAttentionList pending={pending_actions} companyId={companyId} />
        </div>
        <div className="mt-4 grid grid-cols-2 gap-4">
          <PlanningSummaryCard planning={planning} companyId={companyId} />
          <MissionSummaryCard missions={missions} companyId={companyId} />
        </div>
        <div className="mt-4 grid grid-cols-2 gap-4">
          <OrganizationSummaryCard organization={organization} companyId={companyId} />
          <RecentActivityList items={recent_activity} />
        </div>
      </div>
    </main>
  );
}
