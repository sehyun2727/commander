"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useState } from "react";
import { invalidateForEvent } from "@/lib/hooks";
import type { Event } from "@/lib/types";
import { useEventStream } from "@/lib/useEventStream";

const RealtimeEventsContext = createContext<Event[]>([]);

/** Rolling buffer of live events pushed over this company's SSE connection, newest first. */
export function useRealtimeEvents() {
  return useContext(RealtimeEventsContext);
}

export function RealtimeProvider({ companyId, children }: { companyId: string; children: React.ReactNode }) {
  const qc = useQueryClient();
  const [events, setEvents] = useState<Event[]>([]);

  useEventStream(companyId, (event) => {
    setEvents((prev) => (prev.some((e) => e.id === event.id) ? prev : [event, ...prev].slice(0, 100)));
    const taskId = (event.payload as { task_id?: string }).task_id ?? null;
    invalidateForEvent(qc, companyId, taskId);
  });

  return <RealtimeEventsContext.Provider value={events}>{children}</RealtimeEventsContext.Provider>;
}
