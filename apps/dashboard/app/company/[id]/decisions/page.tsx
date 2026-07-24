"use client";

import { useMemo, useState } from "react";
import { DecisionCard } from "@/components/DecisionCard";
import { taskStatusWord } from "@/components/StatusWord";
import { useApprovalHistory, useApprovals, useEmployees, useMissions } from "@/lib/hooks";
import type { Approval } from "@/lib/types";
import { StatusWord as StatusWordToken } from "@/lib/types";

const TABS = [
  { key: "pending", label: "Pending" },
  { key: "history", label: "History" },
] as const;

function outcomeForTask(state: string | undefined): string {
  if (!state) return "";
  switch (taskStatusWord(state)) {
    case StatusWordToken.COMPLETED:
      return "Mission completed.";
    case StatusWordToken.CANCELLED:
      return "Mission cancelled.";
    case StatusWordToken.FAILED:
      return "Mission failed.";
    default:
      return "Mission is still in progress.";
  }
}

export default function DecisionsPage({ params }: { params: { id: string } }) {
  const companyId = params.id;
  const [tab, setTab] = useState<(typeof TABS)[number]["key"]>("pending");
  const { data: pending, isLoading: pendingLoading } = useApprovals(companyId);
  const { data: history, isLoading: historyLoading } = useApprovalHistory(companyId);
  const { data: missions } = useMissions(companyId);
  const { data: employees } = useEmployees(companyId);

  const missionById = useMemo(() => new Map((missions ?? []).map((t) => [t.id, t])), [missions]);
  const employeeById = useMemo(() => new Map((employees ?? []).map((e) => [e.id, e])), [employees]);

  const decided = (history ?? []).filter((a) => a.status !== "pending");
  const items: Approval[] = tab === "pending" ? pending ?? [] : decided;
  const isLoading = tab === "pending" ? pendingLoading : historyLoading;

  return (
    <main className="mx-auto max-w-3xl px-8 py-10">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-text">Decisions</h1>
        <p className="mt-1 text-sm text-text-muted">Every call the Department has needed from you.</p>
      </header>

      <div className="mb-6 flex gap-1 border-b border-base-border">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-3 py-2 text-sm font-medium transition-colors ${
              tab === t.key ? "border-b-2 border-accent text-text" : "text-text-faint hover:text-text-muted"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <p className="text-sm text-text-muted">Loading decisions…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-text-faint">
          {tab === "pending" ? "Nothing needs your decision." : "No decisions yet."}
        </p>
      ) : (
        <div className="space-y-3">
          {items.map((approval) => (
            <DecisionCard
              key={approval.id}
              approval={approval}
              companyId={companyId}
              missionTitle={missionById.get(approval.task_id)?.title ?? "Mission"}
              reviewerColor={
                (approval.reviewer_agent_id && employeeById.get(approval.reviewer_agent_id)?.avatar_color) || undefined
              }
              outcome={tab === "history" ? outcomeForTask(missionById.get(approval.task_id)?.state) : undefined}
              codeStats={missionById.get(approval.task_id)?.code_stats}
            />
          ))}
        </div>
      )}
    </main>
  );
}
