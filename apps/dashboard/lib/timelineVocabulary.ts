import type { Event } from "@/lib/types";
import { EventType } from "@/lib/types";

// The "hidden set" for CEO view (UX_SPEC §3.5: "CEO view hides L3
// mechanism rows -- provider retries, model resolution, heartbeat-ish
// noise"). Defined once as data so both the CEO/Technical toggle and
// digest grouping share a single definition of "minor" -- no scattered
// per-row conditionals.
export const MECHANISM_EVENT_TYPES: ReadonlySet<EventType> = new Set([
  EventType.TASK_STATE_CHANGED,
  EventType.AGENT_STATE_CHANGED,
  EventType.PROVIDER_RETRIED,
  EventType.SYSTEM_HEARTBEAT,
  EventType.WORKSPACE_FILE_CHANGED,
]);

export function isMechanismEvent(event: Event): boolean {
  return MECHANISM_EVENT_TYPES.has(event.type);
}

const DECISION_EVENT_TYPES: ReadonlySet<EventType> = new Set([
  EventType.APPROVAL_REQUESTED,
  EventType.APPROVAL_GRANTED,
  EventType.APPROVAL_REJECTED,
  EventType.APPROVAL_CHANGES_REQUESTED,
]);

export function isDecisionEvent(event: Event): boolean {
  return DECISION_EVENT_TYPES.has(event.type);
}

export type TimelineFilterKey = "all" | "meetings" | "decisions" | "system";

export const TIMELINE_FILTERS: { key: TimelineFilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "meetings", label: "Meetings" },
  { key: "decisions", label: "Decisions" },
  { key: "system", label: "System" },
];

export function matchesTimelineFilter(event: Event, filter: TimelineFilterKey): boolean {
  switch (filter) {
    case "meetings":
      return event.kind === "conversation";
    case "decisions":
      return isDecisionEvent(event);
    case "system":
      return event.kind === "system" && !isDecisionEvent(event);
    default:
      return true;
  }
}

export type TimelineRow = { kind: "event"; event: Event } | { kind: "digest"; events: Event[] };

const DIGEST_THRESHOLD = 4;

/** Groups runs of 4+ consecutive mechanism events into a single digest
 * row. Only meaningful in Technical view -- CEO view already filters
 * mechanism events out entirely, so there is nothing left to digest. */
export function groupForDigest(events: Event[]): TimelineRow[] {
  const rows: TimelineRow[] = [];
  let run: Event[] = [];

  function flushRun() {
    if (run.length >= DIGEST_THRESHOLD) {
      rows.push({ kind: "digest", events: run });
    } else {
      for (const event of run) rows.push({ kind: "event", event });
    }
    run = [];
  }

  for (const event of events) {
    if (isMechanismEvent(event)) {
      run.push(event);
    } else {
      flushRun();
      rows.push({ kind: "event", event });
    }
  }
  flushRun();
  return rows;
}
