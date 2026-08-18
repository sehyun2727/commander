import Link from "next/link";
import { StatusWord, taskStatusWord } from "@/components/StatusWord";
import type { MissionSummary } from "@/lib/types";

export function MissionSummaryCard({ missions, companyId }: { missions: MissionSummary; companyId: string }) {
  return (
    <section className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-text-faint">Missions</h2>
        <Link href={`/company/${companyId}/missions`} className="text-xs text-accent hover:text-accent-hover">
          View all →
        </Link>
      </div>
      {missions.active.length === 0 ? (
        <p className="text-sm text-text-faint">No active missions.</p>
      ) : (
        <ul className="space-y-2">
          {missions.active.slice(0, 5).map((mission) => (
            <li key={mission.id}>
              <Link
                href={`/company/${companyId}/missions/${mission.id}`}
                className="flex items-center justify-between gap-2 rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm transition-colors hover:border-accent/40"
              >
                <span className="truncate text-text">{mission.title}</span>
                <StatusWord token={taskStatusWord(mission.state)} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
