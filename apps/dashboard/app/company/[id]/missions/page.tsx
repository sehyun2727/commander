"use client";

import { MissionCard } from "@/components/MissionCard";
import { NewMissionForm } from "@/components/NewMissionForm";
import { useMissions } from "@/lib/hooks";
import type { Task } from "@/lib/types";

const COLUMNS: { key: string; label: string; match: (state: string) => boolean }[] = [
  { key: "backlog", label: "Backlog", match: (s) => s === "created" },
  {
    key: "in_progress",
    label: "In Progress",
    match: (s) => ["assigned", "in_progress", "in_review", "retrying"].includes(s),
  },
  { key: "needs_decision", label: "Needs CEO Decision", match: (s) => s === "pending_approval" },
  { key: "done", label: "Done", match: (s) => ["completed", "cancelled", "failed"].includes(s) },
];

export default function MissionsPage({ params }: { params: { id: string } }) {
  const companyId = params.id;
  const { data: missions, isLoading } = useMissions(companyId);

  const grouped = (missions ?? []).reduce<Record<string, Task[]>>((acc, task) => {
    const column = COLUMNS.find((c) => c.match(task.state));
    const key = column?.key ?? "backlog";
    (acc[key] ??= []).push(task);
    return acc;
  }, {});

  return (
    <main className="mx-auto max-w-6xl px-8 py-10">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">Missions</h1>
          <p className="mt-1 text-sm text-text-muted">What the Department is working on, end to end.</p>
        </div>
        <NewMissionForm companyId={companyId} />
      </header>

      {isLoading ? (
        <p className="text-sm text-text-muted">Loading missions…</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          {COLUMNS.map((column) => (
            <div key={column.key} className="rounded-xl border border-base-border bg-base-raised/60 p-3">
              <p className="mb-3 px-1 text-xs font-semibold uppercase tracking-wide text-text-faint">
                {column.label} ({grouped[column.key]?.length ?? 0})
              </p>
              <div className="space-y-2.5">
                {(grouped[column.key] ?? []).map((mission) => (
                  <MissionCard key={mission.id} mission={mission} companyId={companyId} />
                ))}
                {(grouped[column.key]?.length ?? 0) === 0 && (
                  <p className="px-1 py-4 text-center text-xs text-text-faint">Nothing here.</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
