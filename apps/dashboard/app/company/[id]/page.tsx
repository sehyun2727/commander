"use client";

import { useMemo } from "react";
import { ApprovalCard } from "@/components/ApprovalCard";
import { useRealtimeEvents } from "@/components/RealtimeProvider";
import { TimelineFeed } from "@/components/TimelineFeed";
import { useApprovals, useCompanyCosts, useEmployees, useMissions, useTimeline } from "@/lib/hooks";
import { formatUsd } from "@/lib/utils";

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <p className="text-xs uppercase tracking-wide text-text-faint">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-text">{value}</p>
    </div>
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

  const activeMissions = missions?.filter((t) => !["completed", "cancelled"].includes(t.state)).length ?? 0;
  const pending = approvals?.filter((a) => a.status === "pending") ?? [];
  const missionById = useMemo(() => new Map((missions ?? []).map((t) => [t.id, t])), [missions]);

  const feedEvents = liveEvents.length > 0 ? liveEvents : timelinePage?.items.slice().reverse() ?? [];

  return (
    <main className="mx-auto max-w-5xl px-8 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-text">Headquarters</h1>
        <p className="mt-1 text-sm text-text-muted">Live view of everything happening across your company.</p>
      </header>

      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-4">
        <StatCard label="Active Missions" value={activeMissions} />
        <StatCard label="Employees" value={employees?.length ?? 0} />
        <StatCard label="Pending CEO Decisions" value={pending.length} />
        <StatCard label="Payroll (this month)" value={formatUsd(costs?.month_total_usd ?? 0)} />
      </div>

      {pending.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-3 text-sm font-semibold text-text">CEO Decisions</h2>
          <div className="space-y-3">
            {pending.map((approval) => (
              <ApprovalCard
                key={approval.id}
                approval={approval}
                companyId={companyId}
                missionTitle={missionById.get(approval.task_id)?.title ?? "Mission"}
              />
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="mb-3 text-sm font-semibold text-text">Timeline</h2>
        <div className="rounded-xl border border-base-border bg-base-card px-4 shadow-panel">
          <TimelineFeed events={feedEvents} />
        </div>
      </section>
    </main>
  );
}
