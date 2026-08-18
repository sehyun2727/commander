import Link from "next/link";
import type { PlanningSummary } from "@/lib/types";

export function PlanningSummaryCard({ planning, companyId }: { planning: PlanningSummary; companyId: string }) {
  return (
    <section className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-text-faint">Planning</h2>
        <Link href={`/company/${companyId}/specifications`} className="text-xs text-accent hover:text-accent-hover">
          View all →
        </Link>
      </div>
      {!planning.active ? (
        <p className="text-sm text-text-faint">No active planning.</p>
      ) : (
        <div className="text-sm">
          <p className="capitalize text-text">
            {planning.status ?? "active"} · v{planning.current_version ?? 1}
          </p>
          <p className="mt-0.5 text-xs text-text-faint">
            {planning.turn_count ?? 0} turn{planning.turn_count === 1 ? "" : "s"}
            {planning.unresolved_questions > 0 &&
              ` · ${planning.unresolved_questions} open question${planning.unresolved_questions === 1 ? "" : "s"}`}
          </p>
          {planning.specification_id && (
            <Link
              href={`/company/${companyId}/specifications/${planning.specification_id}`}
              className="mt-2 inline-block text-accent hover:text-accent-hover"
            >
              Open specification →
            </Link>
          )}
        </div>
      )}
    </section>
  );
}
