import Link from "next/link";
import { AgentAvatar } from "@/components/AgentAvatar";
import { StatusPill } from "@/components/StatusPill";
import type { Agent, Task } from "@/lib/types";
import { agentStateLabel, agentStateTone, formatUsd, roleLabel } from "@/lib/utils";

export function EmployeeCard({
  employee,
  companyId,
  currentMission,
  spendUsd,
}: {
  employee: Agent;
  companyId: string;
  currentMission?: Task;
  spendUsd?: number;
}) {
  return (
    <div className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <div className="flex items-center gap-3">
        <AgentAvatar name={employee.name} color={employee.avatar_color} size={44} />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-text">{employee.name}</p>
          <p className="text-xs uppercase tracking-wide text-text-faint">{roleLabel(employee.role)}</p>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2">
        <StatusPill tone={agentStateTone(employee.state)} label={agentStateLabel(employee.state)} />
        {!!spendUsd && <span className="text-xs text-text-faint">{formatUsd(spendUsd)} this month</span>}
      </div>
      {currentMission && (
        <Link
          href={`/company/${companyId}/missions/${currentMission.id}`}
          className="mt-3 block truncate rounded-lg bg-base-hover px-2.5 py-1.5 text-xs text-text-muted hover:text-text"
        >
          On: {currentMission.title}
        </Link>
      )}
    </div>
  );
}
