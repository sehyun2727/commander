"use client";

import { useState } from "react";
import { ErrorState } from "@/components/ErrorState";
import { WorkspaceEditMode } from "@/components/workspace/WorkspaceEditMode";
import { WorkspaceWidgetGrid } from "@/components/workspace/WorkspaceWidgetGrid";
import { useWorkspaceOverview, useWorkspacePreferences, useWorkspaceWidgets } from "@/lib/hooks";

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

// Sprint 14 introduced this page as the real CEO Workspace; Sprint 15
// converts its fixed widget composition into a registry-driven one
// (§7.1, DECISIONS.md #228) -- the actual widgets, their data, and their
// business meaning are unchanged and still come straight from the Sprint
// 13 WorkspaceSnapshot contract (this page never recomputes next_action's
// precedence), but *which* widgets render and in *what order* is now the
// CEO's own per-company preference, not a hardcoded layout.
export default function WorkspacePage({ params }: { params: { id: string } }) {
  const companyId = params.id;
  const [editMode, setEditMode] = useState(false);
  const { data: snapshot, isLoading: snapshotLoading, isError: snapshotError, refetch } = useWorkspaceOverview(companyId);
  const { data: catalog, isLoading: catalogLoading, isError: catalogError } = useWorkspaceWidgets(companyId);
  const { data: preferences, isLoading: prefsLoading, isError: prefsError } = useWorkspacePreferences(companyId);

  if (editMode) {
    return (
      <WorkspaceEditMode companyId={companyId} catalog={catalog ?? []} onClose={() => setEditMode(false)} />
    );
  }

  if (snapshotLoading || catalogLoading || prefsLoading) {
    return <WorkspaceSkeleton />;
  }

  if (snapshotError || catalogError || prefsError || !snapshot || !catalog || !preferences) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-8 sm:py-10">
        <header className="mb-6">
          <h1 className="text-2xl font-semibold text-text">CEO Workspace</h1>
        </header>
        <ErrorState description="Couldn't load the CEO Workspace. Try refreshing in a moment." />
      </main>
    );
  }

  const visibleEntries = [...preferences.widgets].filter((w) => w.visible).sort((a, b) => a.order - b.order);

  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:px-8 sm:py-10">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold text-text">{snapshot.project.name}</h1>
          <p className="mt-1 text-sm text-text-muted">CEO Workspace — everything that needs you, in one place.</p>
        </div>
        <button
          type="button"
          onClick={() => setEditMode(true)}
          className="rounded-lg border border-base-border px-4 py-2 text-sm font-medium text-text hover:bg-base-hover"
        >
          Customize Workspace
        </button>
      </header>

      <WorkspaceWidgetGrid
        entries={visibleEntries}
        snapshot={snapshot}
        companyId={companyId}
        onRefresh={() => refetch()}
        catalog={catalog}
      />
    </main>
  );
}
