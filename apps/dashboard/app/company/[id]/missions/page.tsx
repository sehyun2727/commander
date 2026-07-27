"use client";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { MissionCard } from "@/components/MissionCard";
import { NewMissionForm } from "@/components/NewMissionForm";
import { taskStatusWord } from "@/components/StatusWord";
import { useCreateMission, useMissions, useStarters } from "@/lib/hooks";
import { StatusWord as StatusWordToken } from "@/lib/types";
import type { Task } from "@/lib/types";

// Kanban lanes per UX_SPEC §3.3, derived from the same StatusWord token
// every other status render site uses — no second internal-state list.
const COLUMNS: { key: string; label: string; tokens: StatusWordToken[]; emptyText: string }[] = [
  { key: "backlog", label: "Backlog", tokens: [StatusWordToken.PLANNING], emptyText: "Nothing queued yet." },
  {
    key: "developing",
    label: "Developing",
    tokens: [StatusWordToken.DEVELOPING, StatusWordToken.REVIEWING],
    emptyText: "Nobody's building right now.",
  },
  {
    key: "needs_decision",
    label: "Needs your decision",
    tokens: [StatusWordToken.NEEDS_DECISION],
    emptyText: "Nothing waiting on you.",
  },
  {
    key: "done",
    label: "Done",
    tokens: [StatusWordToken.COMPLETED, StatusWordToken.FAILED, StatusWordToken.CANCELLED],
    emptyText: "Nothing finished yet.",
  },
];

export default function MissionsPage({ params }: { params: { id: string } }) {
  const companyId = params.id;
  const { data: missions, isLoading, isError } = useMissions(companyId);
  const { data: starters } = useStarters(companyId);
  const createMission = useCreateMission(companyId);
  const starter = starters?.[0];

  const grouped = (missions ?? []).reduce<Record<string, Task[]>>((acc, task) => {
    const token = taskStatusWord(task.state);
    const column = COLUMNS.find((c) => c.tokens.includes(token));
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
      ) : isError ? (
        <ErrorState description="Couldn't load Missions. Try refreshing in a moment." />
      ) : missions?.length === 0 ? (
        <EmptyState
          title="No Missions yet"
          description={
            starter
              ? `Not sure where to start? Try: "${starter.title}" — ${starter.description}`
              : "Give the Department its first brief above."
          }
          action={
            starter && (
              <button
                onClick={() =>
                  createMission.mutate({ title: starter.title, description: starter.description, priority: "normal" })
                }
                disabled={createMission.isPending}
                className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
              >
                {createMission.isPending ? "Creating…" : `Create: ${starter.title}`}
              </button>
            )
          }
        />
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
                  <p className="px-1 py-4 text-center text-xs text-text-faint">{column.emptyText}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
