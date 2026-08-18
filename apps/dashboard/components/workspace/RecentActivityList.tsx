import { EmptyState } from "@/components/EmptyState";
import type { ActivityItem } from "@/lib/types";
import { relativeTime } from "@/lib/utils";

// §4.6: safe activity summaries only -- actor/role label, timestamp,
// event/status distinction, bounded list, empty state. Never raw event
// payloads or hidden reasoning; `item.reason` is already the same
// human-readable string the Timeline itself shows.
export function RecentActivityList({ items }: { items: ActivityItem[] }) {
  return (
    <section className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-faint">Recent activity</h2>
      {items.length === 0 ? (
        <EmptyState title="No activity yet" description="Nothing has happened in this Company yet." />
      ) : (
        <ul className="space-y-2">
          {items.slice(0, 10).map((item) => (
            <li key={item.id} className="rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="truncate text-text-muted">
                  {item.actor_name} · {item.kind}
                </span>
                <span className="shrink-0 text-xs text-text-faint">{relativeTime(item.created_at)}</span>
              </div>
              {item.reason && <p className="mt-1 truncate text-xs text-text-faint">{item.reason}</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
