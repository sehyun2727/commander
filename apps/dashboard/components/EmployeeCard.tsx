import Link from "next/link";
import { AgentAvatar } from "@/components/AgentAvatar";
import { StatusWord, agentStatusWord } from "@/components/StatusWord";
import type { Agent, Role, Task } from "@/lib/types";
import { formatUsd, roleLabel, styleSummary } from "@/lib/utils";

export function EmployeeCard({
  employee,
  companyId,
  currentMission,
  spendUsd,
  roles,
}: {
  employee: Agent;
  companyId: string;
  currentMission?: Task;
  spendUsd?: number;
  roles?: Role[];
}) {
  return (
    <div className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel transition hover:border-accent/50">
      <Link href={`/company/${companyId}/employees/${employee.id}`} className="block">
        <div className="flex items-center gap-3">
          <AgentAvatar name={employee.name} color={employee.avatar_color} size={44} />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-text">{employee.name}</p>
            <p className="text-xs uppercase tracking-wide text-text-faint">{roleLabel(roles, employee.role)}</p>
          </div>
        </div>
        <p className="mt-2 truncate text-xs text-text-faint">{styleSummary(employee.profile)}</p>
      </Link>
      <div className="mt-3 flex items-center justify-between gap-2">
        <StatusWord token={agentStatusWord(employee.state)} />
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
