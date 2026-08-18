"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useRef, useState } from "react";
import { invalidateForEvent, keys } from "@/lib/hooks";
import { EventType } from "@/lib/types";
import type { Event } from "@/lib/types";
import type { ConnectionStatus } from "@/lib/useEventStream";
import { useEventStream } from "@/lib/useEventStream";

const RealtimeEventsContext = createContext<Event[]>([]);
const ConnectionStatusContext = createContext<ConnectionStatus>("connecting");
const LastEventAtContext = createContext<number | null>(null);

interface StreamingReply {
  agentId: string;
  text: string;
}

const StreamingRepliesContext = createContext<Record<string, StreamingReply>>({});

/** Rolling buffer of live persisted events pushed over this company's SSE connection, newest first. */
export function useRealtimeEvents() {
  return useContext(RealtimeEventsContext);
}

/** The in-flight, not-yet-persisted reply streaming into a Mission's Meeting, if any. */
export function useStreamingReply(taskId: string): StreamingReply | null {
  return useContext(StreamingRepliesContext)[taskId] ?? null;
}

/** Live status of this company's SSE connection, for a small "Reconnecting.../stale" indicator. */
export function useRealtimeConnectionStatus(): ConnectionStatus {
  return useContext(ConnectionStatusContext);
}

/** Timestamp (ms) of the last SSE frame received (event or heartbeat), for a "last updated" readout. */
export function useRealtimeLastEventAt(): number | null {
  return useContext(LastEventAtContext);
}

export function RealtimeProvider({ companyId, children }: { companyId: string; children: React.ReactNode }) {
  const qc = useQueryClient();
  const [events, setEvents] = useState<Event[]>([]);
  const [streaming, setStreaming] = useState<Record<string, StreamingReply>>({});

  const { status: connectionStatus, lastMessageAt } = useEventStream(companyId, (event) => {
    if (event.type === EventType.CONVERSATION_MESSAGE_DELTA) {
      const payload = event.payload as { text: string; agent_id?: string; task_id?: string; done?: boolean };
      const taskId = payload.task_id;
      if (!taskId) return;
      if (payload.done) {
        // Keep the bubble on screen briefly after the reply finishes
        // streaming, so it doesn't flash away before the persisted
        // conversation.message has round-tripped through query invalidation.
        setTimeout(() => {
          setStreaming((prev) => {
            const next = { ...prev };
            delete next[taskId];
            return next;
          });
        }, 400);
        return;
      }
      setStreaming((prev) => {
        const existing = prev[taskId];
        return {
          ...prev,
          [taskId]: { agentId: payload.agent_id ?? existing?.agentId ?? "", text: (existing?.text ?? "") + payload.text },
        };
      });
      return;
    }

    // Deltas are transient (never persisted) — only persisted events belong
    // in the Timeline narration buffer and trigger a query refetch.
    setEvents((prev) => (prev.some((e) => e.id === event.id) ? prev : [event, ...prev].slice(0, 100)));
    const taskId = (event.payload as { task_id?: string }).task_id ?? null;
    const agentId = (event.payload as { agent_id?: string }).agent_id ?? null;
    const specificationId = (event.payload as { specification_id?: string }).specification_id ?? null;
    invalidateForEvent(qc, companyId, taskId, agentId, specificationId);
  });

  // §4.7 "when event continuity is uncertain, refetch a fresh snapshot":
  // a resumed connection may have missed events entirely, so incremental
  // per-event invalidation alone isn't trustworthy — pull a fresh Workspace
  // snapshot the moment the connection comes back from reconnecting/stale.
  const prevStatusRef = useRef<ConnectionStatus>(connectionStatus);
  useEffect(() => {
    const prev = prevStatusRef.current;
    if (connectionStatus === "open" && (prev === "reconnecting" || prev === "stale")) {
      qc.invalidateQueries({ queryKey: keys.workspaceOverview(companyId) });
    }
    prevStatusRef.current = connectionStatus;
  }, [connectionStatus, companyId, qc]);

  return (
    <ConnectionStatusContext.Provider value={connectionStatus}>
      <LastEventAtContext.Provider value={lastMessageAt}>
        <RealtimeEventsContext.Provider value={events}>
          <StreamingRepliesContext.Provider value={streaming}>{children}</StreamingRepliesContext.Provider>
        </RealtimeEventsContext.Provider>
      </LastEventAtContext.Provider>
    </ConnectionStatusContext.Provider>
  );
}
