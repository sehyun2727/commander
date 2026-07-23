"use client";

import { useEffect, useRef } from "react";
import { api } from "./api";
import type { Event } from "./types";

/**
 * One SSE connection per company. Replays the last 50 events on connect
 * (server-side), then delivers live ones as they're published. Heartbeats
 * are sent as a separate SSE `event:` name and are ignored here — they
 * only exist so idle connections/proxies don't time out.
 */
export function useEventStream(companyId: string | undefined, onEvent: (event: Event) => void) {
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  useEffect(() => {
    if (!companyId) return;

    const source = new EventSource(api.streamUrl(companyId));
    const handleMessage = (message: MessageEvent<string>) => {
      try {
        handlerRef.current(JSON.parse(message.data) as Event);
      } catch {
        // ignore malformed frames
      }
    };
    source.addEventListener("commander-event", handleMessage);

    return () => {
      source.removeEventListener("commander-event", handleMessage);
      source.close();
    };
  }, [companyId]);
}
