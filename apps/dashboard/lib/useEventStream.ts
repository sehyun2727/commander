"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Event } from "./types";

export type ConnectionStatus = "connecting" | "open" | "reconnecting";

/**
 * One SSE connection per company. Replays the last 50 events on connect
 * (server-side), then delivers live ones as they're published. Heartbeats
 * are sent as a separate SSE `event:` name and are ignored here — they
 * only exist so idle connections/proxies don't time out.
 *
 * The browser's native EventSource already retries indefinitely on its own
 * after a drop (no bounded-retry logic needed here) — this hook only adds
 * a status so the UI can show "Reconnecting..." instead of silently
 * missing live updates until the connection comes back.
 */
export function useEventStream(companyId: string | undefined, onEvent: (event: Event) => void): ConnectionStatus {
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;
  const [status, setStatus] = useState<ConnectionStatus>("connecting");

  useEffect(() => {
    if (!companyId) return;
    setStatus("connecting");

    const source = new EventSource(api.streamUrl(companyId));
    const handleMessage = (message: MessageEvent<string>) => {
      try {
        handlerRef.current(JSON.parse(message.data) as Event);
      } catch {
        // ignore malformed frames
      }
    };
    source.addEventListener("commander-event", handleMessage);
    source.addEventListener("open", () => setStatus("open"));
    // The browser retries on its own after any drop (we never call
    // source.close() outside cleanup below), so every "error" here means
    // "reconnecting", not "gave up".
    source.addEventListener("error", () => setStatus("reconnecting"));

    return () => {
      source.removeEventListener("commander-event", handleMessage);
      source.close();
    };
  }, [companyId]);

  return status;
}
