import Link from "next/link";
import type { Focus } from "@/lib/types";

// Allowlisted per resource_type — the same closed set next_action.py's
// own facts use (task/specification/role) — not an arbitrary route build.
function focusRoute(companyId: string, focus: Focus): string | null {
  if (!focus.resource_type || !focus.resource_id) return null;
  switch (focus.resource_type) {
    case "task":
      return `/company/${companyId}/missions/${focus.resource_id}`;
    case "specification":
      return `/company/${companyId}/specifications/${focus.resource_id}`;
    case "role":
      return `/company/${companyId}/employees`;
    default:
      return null;
  }
}

export function CurrentFocusCard({ focus, companyId }: { focus: Focus; companyId: string }) {
  const route = focusRoute(companyId, focus);
  return (
    <section className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-faint">Current focus</h2>
      {!focus.resource_type ? (
        <p className="text-sm text-text-faint">Nothing specific in focus right now.</p>
      ) : (
        <div className="text-sm">
          <p className="capitalize text-text-muted">
            {focus.resource_type} · {focus.status ?? "—"}
          </p>
          {route && (
            <Link href={route} className="mt-1 inline-block text-accent hover:text-accent-hover">
              View →
            </Link>
          )}
        </div>
      )}
    </section>
  );
}
