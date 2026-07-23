"use client";

import Link from "next/link";
import { useAssignMission } from "@/lib/hooks";
import type { Task } from "@/lib/types";
import { taskStateLabel, taskStateTone } from "@/lib/utils";
import { StatusPill } from "./StatusPill";

const PRIORITY_LABEL: Record<string, string> = { low: "Low", normal: "Normal", high: "High", urgent: "Urgent" };

export function MissionCard({ mission, companyId }: { mission: Task; companyId: string }) {
  const assign = useAssignMission(companyId);

  return (
    <div className="rounded-lg border border-base-border bg-base-card p-3.5 shadow-panel transition-colors hover:border-accent/40">
      <Link href={`/company/${companyId}/missions/${mission.id}`} className="block">
        <p className="text-sm font-medium text-text">{mission.title}</p>
        {mission.description && <p className="mt-1 line-clamp-2 text-xs text-text-muted">{mission.description}</p>}
      </Link>
      <div className="mt-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <StatusPill tone={taskStateTone(mission.state)} label={taskStateLabel(mission.state)} />
          <span className="text-[11px] uppercase tracking-wide text-text-faint">
            {PRIORITY_LABEL[mission.priority] ?? mission.priority}
          </span>
        </div>
        {mission.state === "created" && (
          <button
            onClick={() => assign.mutate(mission.id)}
            disabled={assign.isPending}
            className="rounded-md bg-accent px-2.5 py-1 text-[11px] font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {assign.isPending ? "Assigning…" : "Assign"}
          </button>
        )}
      </div>
      {mission.attempt > 1 && <p className="mt-2 text-[11px] text-text-faint">Attempt {mission.attempt}</p>}
    </div>
  );
}
