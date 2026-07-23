import type { Event } from "@/lib/types";
import { narrate, relativeTime } from "@/lib/utils";

const ACTOR_DOT: Record<string, string> = {
  ceo: "bg-accent",
  employee: "bg-status-green",
  system: "bg-status-gray",
};

export function TimelineFeed({ events, emptyLabel = "No activity yet." }: { events: Event[]; emptyLabel?: string }) {
  if (events.length === 0) {
    return <p className="px-1 py-6 text-center text-sm text-text-faint">{emptyLabel}</p>;
  }

  return (
    <ol className="space-y-0">
      {events.map((event) => (
        <li key={event.id} className="flex gap-3 border-b border-base-border/60 px-1 py-3 last:border-none">
          <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${ACTOR_DOT[event.actor.role] ?? "bg-status-gray"}`} />
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-medium text-text-muted">{event.actor.name}</p>
            <p className="mt-0.5 whitespace-pre-wrap text-sm text-text">{narrate(event)}</p>
          </div>
          <span className="shrink-0 pt-0.5 text-[11px] text-text-faint">{relativeTime(event.created_at)}</span>
        </li>
      ))}
    </ol>
  );
}
