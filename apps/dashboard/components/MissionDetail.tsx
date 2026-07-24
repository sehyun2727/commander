"use client";

import Link from "next/link";
import { ChangeSummaryCard } from "@/components/ChangeSummaryCard";
import { ChatThread } from "@/components/ChatThread";
import { DecisionCard } from "@/components/DecisionCard";
import { StatusWord, taskStatusWord } from "@/components/StatusWord";
import { useApprovals, useAssignMission, useEmployees, useMission, useMissionCosts } from "@/lib/hooks";
import { formatUsd } from "@/lib/utils";

export function MissionDetail({ companyId, taskId }: { companyId: string; taskId: string }) {
  const { data: mission, isLoading } = useMission(taskId);
  const { data: approvals } = useApprovals(companyId);
  const { data: costs } = useMissionCosts(taskId);
  const { data: employees } = useEmployees(companyId);
  const assign = useAssignMission(companyId);

  const pendingApproval = approvals?.find((a) => a.task_id === taskId && a.status === "pending");
  const reviewer = pendingApproval
    ? employees?.find((e) => e.id === pendingApproval.reviewer_agent_id)
    : undefined;

  if (isLoading || !mission) {
    return (
      <main className="mx-auto max-w-3xl px-8 py-10">
        <p className="text-sm text-text-muted">Loading mission…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-8 py-10">
      <Link href={`/company/${companyId}/missions`} className="text-xs font-medium text-text-faint hover:text-text-muted">
        ← Missions
      </Link>

      <header className="mt-3 mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-text">{mission.title}</h1>
          {mission.description && <p className="mt-2 text-sm text-text-muted">{mission.description}</p>}
        </div>
        {mission.state === "created" && (
          <button
            onClick={() => assign.mutate(mission.id)}
            disabled={assign.isPending}
            className="shrink-0 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {assign.isPending ? "Assigning…" : "Assign to Department"}
          </button>
        )}
      </header>

      <div className="mb-6 flex flex-wrap items-center gap-2">
        <StatusWord token={taskStatusWord(mission.state)} />
        <span className="text-xs uppercase tracking-wide text-text-faint">Priority: {mission.priority}</span>
        {mission.attempt > 1 && <span className="text-xs text-text-faint">Attempt {mission.attempt}</span>}
        {costs && costs.total_usd > 0 && (
          <span className="text-xs text-text-faint">Mission Budget spent: {formatUsd(costs.total_usd)}</span>
        )}
      </div>

      {pendingApproval && (
        <div className="mb-6">
          <DecisionCard
            approval={pendingApproval}
            companyId={companyId}
            missionTitle={mission.title}
            reviewerColor={reviewer?.avatar_color}
            linkToMission={false}
          />
        </div>
      )}

      {mission.result_markdown && (
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold text-text">Latest Deliverable</h2>
          {mission.deliverable_type === "code" && mission.code_stats ? (
            <ChangeSummaryCard
              taskId={taskId}
              summary={mission.result_markdown}
              stats={mission.code_stats}
              verdict={pendingApproval?.status}
            />
          ) : (
            <div className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
              <pre className="whitespace-pre-wrap font-sans text-sm text-text-muted">{mission.result_markdown}</pre>
            </div>
          )}
        </section>
      )}

      <section>
        <h2 className="mb-2 text-sm font-semibold text-text">Meeting</h2>
        <ChatThread companyId={companyId} taskId={taskId} />
      </section>
    </main>
  );
}
