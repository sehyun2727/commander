"use client";

import Link from "next/link";
import { useMemo } from "react";
import { DecisionCard } from "@/components/DecisionCard";
import { useRealtimeEvents } from "@/components/RealtimeProvider";
import { SituationReport } from "@/components/SituationReport";
import { agentStatusWord, taskStatusWord } from "@/components/StatusWord";
import { TimelineFeed } from "@/components/TimelineFeed";
import { useApprovals, useCompanyCosts, useEmployees, useMissions, useTimeline } from "@/lib/hooks";
import { StatusWord as StatusWordToken } from "@/lib/types";
import { formatUsd } from "@/lib/utils";

const TERMINAL_TOKENS: StatusWordToken[] = [StatusWordToken.COMPLETED, StatusWordToken.FAILED, StatusWordToken.CANCELLED];

function StatCard({ label, value, href }: { label: string; value: string | number; href: string }) {
  return (
    <Link
      href={href}
      className="block rounded-xl border border-base-border bg-base-card p-4 shadow-panel transition hover:border-accent/50"
    >
      <p className="text-xs uppercase tracking-wide text-text-faint">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-text">{value}</p>
    </Link>
  );
}

export default function HeadquartersPage({ params }: { params: { id: string } }) {
  const companyId = params.id;
  const { data: missions } = useMissions(companyId);
  const { data: employees } = useEmployees(companyId);
  const { data: approvals } = useApprovals(companyId);
  const { data: timelinePage } = useTimeline(companyId);
  const { data: costs } = useCompanyCosts(companyId);
  const liveEvents = useRealtimeEvents();

  const activeMissions = missions?.filter((t) => !TERMINAL_TOKENS.includes(taskStatusWord(t.state))).length ?? 0;
  const risksOpen = missions?.filter((t) => taskStatusWord(t.state) === StatusWordToken.FAILED).length ?? 0;
  const employeesWorking =
    employees?.filter((e) => agentStatusWord(e.state) !== StatusWordToken.IDLE).length ?? 0;
  const pending = approvals?.filter((a) => a.status === "pending") ?? [];
  const missionById = useMemo(() => new Map((missions ?? []).map((t) => [t.id, t])), [missions]);
  const employeeById = useMemo(() => new Map((employees ?? []).map((e) => [e.id, e])), [employees]);

  const feedEvents = liveEvents.length > 0 ? liveEvents : timelinePage?.items ?? [];

  return (
    <main className="mx-auto max-w-5xl px-8 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-text">Headquarters</h1>
        <p className="mt-1 text-sm text-text-muted">Live view of everything happening across your company.</p>
      </header>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold text-text">CEO Decisions</h2>
        {pending.length > 0 ? (
          <div className="space-y-3">
            {pending.map((approval) => (
              <DecisionCard
                key={approval.id}
                approval={approval}
                companyId={companyId}
                missionTitle={missionById.get(approval.task_id)?.title ?? "Mission"}
                reviewerColor={
                  (approval.reviewer_agent_id && employeeById.get(approval.reviewer_agent_id)?.avatar_color) ||
                  undefined
                }
                codeStats={missionById.get(approval.task_id)?.code_stats}
              />
            ))}
          </div>
        ) : (
          <p className="rounded-xl border border-base-border bg-base-card p-4 text-sm text-text-faint shadow-panel">
            Nothing needs your decision.
          </p>
        )}
      </section>

      <div className="mb-8">
        <SituationReport companyId={companyId} />
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-4">
        <StatCard label="Missions active" value={activeMissions} href={`/company/${companyId}/missions`} />
        <StatCard
          label="Employees working now"
          value={employeesWorking}
          href={`/company/${companyId}/employees`}
        />
        <StatCard label="Risks open" value={risksOpen} href={`/company/${companyId}/missions`} />
        <StatCard
          label="Payroll (this month)"
          value={formatUsd(costs?.month_total_usd ?? 0)}
          href={`/company/${companyId}/employees`}
        />
      </div>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-text">Timeline</h2>
          <Link href={`/company/${companyId}/timeline`} className="text-xs text-accent hover:text-accent-hover">
            Open full Timeline →
          </Link>
        </div>
        <div className="rounded-xl border border-base-border bg-base-card px-4 shadow-panel">
          <TimelineFeed events={feedEvents} />
        </div>
      </section>
    </main>
  );
}
