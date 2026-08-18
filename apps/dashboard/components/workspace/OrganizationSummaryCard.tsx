import Link from "next/link";
import type { OrganizationSummary } from "@/lib/types";

export function OrganizationSummaryCard({
  organization,
  companyId,
}: {
  organization: OrganizationSummary;
  companyId: string;
}) {
  return (
    <section className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-text-faint">Organization</h2>
        <Link href={`/company/${companyId}/employees`} className="text-xs text-accent hover:text-accent-hover">
          View all →
        </Link>
      </div>
      <p className="mb-3 text-sm text-text-muted">
        {organization.counts.total} employee{organization.counts.total === 1 ? "" : "s"} · {organization.counts.busy}{" "}
        busy · {organization.counts.idle} idle
        {organization.counts.error > 0 && ` · ${organization.counts.error} error`}
      </p>
      <ul className="space-y-1.5">
        {organization.leadership.map((slot) => (
          <li key={slot.role_key} className="flex items-center justify-between text-sm">
            <span className="text-text-muted">{slot.title}</span>
            <span className={slot.occupied ? "text-text" : "text-status-amber"}>
              {slot.occupied ? slot.employee_name : "Vacant"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
