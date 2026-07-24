"use client";

import { useState } from "react";
import { AgentAvatar } from "@/components/AgentAvatar";
import { groupForDigest, isMechanismEvent } from "@/lib/timelineVocabulary";
import type { TimelineRow } from "@/lib/timelineVocabulary";
import type { Agent, Event } from "@/lib/types";
import { narrate, relativeTime } from "@/lib/utils";

const SYSTEM_DOT: Record<string, string> = {
  ceo: "bg-accent",
  employee: "bg-status-green",
  system: "bg-status-gray",
};

const CEO_AVATAR_COLOR = "#8b5cf6";
const DEFAULT_AVATAR_COLOR = "#64748b";

function MeetingBubble({ event, employeeById }: { event: Event; employeeById?: Map<string, Agent> }) {
  const color =
    event.actor.role === "ceo"
      ? CEO_AVATAR_COLOR
      : employeeById?.get(event.actor.id)?.avatar_color ?? DEFAULT_AVATAR_COLOR;
  return (
    <li className="flex gap-3 border-b border-base-border/60 px-1 py-3 last:border-none">
      <AgentAvatar name={event.actor.name} color={color} size={28} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <p className="text-[13px] font-medium text-text">{event.actor.name}</p>
          <span className="text-[11px] capitalize text-text-faint">{event.actor.role}</span>
        </div>
        <p className="mt-0.5 whitespace-pre-wrap text-sm text-text-muted">{narrate(event)}</p>
      </div>
      <span className="shrink-0 pt-0.5 text-[11px] text-text-faint">{relativeTime(event.created_at)}</span>
    </li>
  );
}

function SystemRow({ event }: { event: Event }) {
  return (
    <li className="flex gap-3 border-b border-base-border/60 px-1 py-2.5 last:border-none">
      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${SYSTEM_DOT[event.actor.role] ?? "bg-status-gray"}`} />
      <p className="min-w-0 flex-1 truncate text-[13px] text-text-muted">{narrate(event)}</p>
      <span className="shrink-0 text-[11px] text-text-faint">{relativeTime(event.created_at)}</span>
    </li>
  );
}

function DigestRow({ events }: { events: Event[] }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="border-b border-base-border/60 px-1 py-2.5 last:border-none">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 text-left text-[13px] text-text-faint hover:text-text-muted"
      >
        <span className="h-2 w-2 shrink-0 rounded-full bg-status-gray" />
        {open ? "Hide routine events" : `${events.length} routine events`}
      </button>
      {open && (
        <ol className="mt-1 space-y-0 border-l border-base-border pl-4">
          {events.map((event) => (
            <SystemRow key={event.id} event={event} />
          ))}
        </ol>
      )}
    </li>
  );
}

// ★ TimelineFeed (UX_SPEC §5): conversation events render as MeetingBubble
// (avatar, name, role, text), system events as compact SystemRow, and --
// in Technical view only -- runs of 4+ consecutive mechanism events (see
// lib/timelineVocabulary) collapse into an expandable DigestRow so the
// feed never reads like a log file. CEO view (the default, and what
// Headquarters' condensed feed uses) filters mechanism events out
// entirely rather than digesting them, since there is nothing routine
// left to show once the noise is gone.
export function TimelineFeed({
  events,
  emptyLabel = "No activity yet.",
  technical = false,
  employeeById,
}: {
  events: Event[];
  emptyLabel?: string;
  technical?: boolean;
  employeeById?: Map<string, Agent>;
}) {
  const visible = technical ? events : events.filter((event) => !isMechanismEvent(event));

  if (visible.length === 0) {
    return <p className="px-1 py-6 text-center text-sm text-text-faint">{emptyLabel}</p>;
  }

  const rows: TimelineRow[] = technical
    ? groupForDigest(visible)
    : visible.map((event) => ({ kind: "event" as const, event }));

  return (
    <ol className="space-y-0">
      {rows.map((row) =>
        row.kind === "digest" ? (
          <DigestRow key={row.events[0].id} events={row.events} />
        ) : row.event.kind === "conversation" ? (
          <MeetingBubble key={row.event.id} event={row.event} employeeById={employeeById} />
        ) : (
          <SystemRow key={row.event.id} event={row.event} />
        )
      )}
    </ol>
  );
}
