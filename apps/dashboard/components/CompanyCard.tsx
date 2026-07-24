"use client";

import Link from "next/link";
import { AgentAvatar } from "@/components/AgentAvatar";
import { StatusWord, agentStatusWord, companyStatusWord, taskStatusWord } from "@/components/StatusWord";
import { useApprovals, useEmployees, useMissions, useTimeline } from "@/lib/hooks";
import { StatusWord as StatusWordToken } from "@/lib/types";
import type { Project } from "@/lib/types";
import { narrate } from "@/lib/utils";

export function CompanyCard({ company }: { company: Project }) {
  const { data: employees } = useEmployees(company.id);
  const { data: missions } = useMissions(company.id);
  const { data: approvals } = useApprovals(company.id);
  const { data: timeline } = useTimeline(company.id);

  const status = companyStatusWord((missions ?? []).map((m) => m.state));
  const completed = (missions ?? []).filter((m) => taskStatusWord(m.state) === StatusWordToken.COMPLETED).length;
  const total = missions?.length ?? 0;
  const progress = total > 0 ? Math.round((completed / total) * 100) : 0;
  const pendingDecisions = approvals?.length ?? 0;
  const latestEvent = timeline?.items[0];

  return (
    <Link
      href={`/company/${company.id}`}
      className="block rounded-xl border border-base-border bg-base-card p-4 shadow-panel transition hover:border-accent/50"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-text">{company.name}</p>
          <p className="mt-0.5 text-xs text-text-faint">Provider: {company.provider}</p>
        </div>
        <StatusWord token={status} />
      </div>

      {!!pendingDecisions && (
        <div className="mt-3 rounded-lg bg-status-amber-soft px-2.5 py-1.5 text-xs font-medium text-status-amber">
          {pendingDecisions} decision{pendingDecisions === 1 ? "" : "s"} waiting on you
        </div>
      )}

      {total > 0 && (
        <div className="mt-3">
          <p className="text-xs text-text-faint">
            {completed}/{total} Missions
          </p>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-base-hover">
            <div className="h-full rounded-full bg-accent" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}

      {!!employees?.length && (
        <div className="mt-3 flex items-center gap-1.5">
          {employees.map((employee) => (
            <div key={employee.id} className="relative">
              <AgentAvatar name={employee.name} color={employee.avatar_color} size={26} />
              {agentStatusWord(employee.state) !== StatusWordToken.IDLE && (
                <span className="absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full border-2 border-base-card bg-status-green" />
              )}
            </div>
          ))}
        </div>
      )}

      {latestEvent && <p className="mt-3 truncate text-xs text-text-faint">{narrate(latestEvent)}</p>}
    </Link>
  );
}
