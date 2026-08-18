"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Event } from "./types";

export type ConnectionStatus = "connecting" | "open" | "reconnecting" | "stale";

// Heartbeats arrive every 15s (realtime/routes.py) purely to keep idle
// connections alive; ~3 missed heartbeats is a real "gone quiet" signal
// rather than a normal lull between domain events (DECISIONS.md #225).
const STALE_AFTER_MS = 40_000;
const STALE_CHECK_INTERVAL_MS = 5_000;

export interface EventStreamState {
  status: ConnectionStatus;
  lastMessageAt: number | null;
}

/**
 * One SSE connection per company. Replays the last 50 events on connect
 * (server-side), then delivers live ones as they're published. Heartbeats
 * are a separate SSE `event:` name; they never reach `onEvent` (not a real
 * domain Event) but do count toward `lastMessageAt`/staleness detection.
 *
 * The browser's native EventSource already retries indefinitely on its own
 * after a drop (no bounded-retry logic needed here) — this hook only adds
 * a status so the UI can show "Reconnecting..."/"stale" instead of
 * silently missing live updates until the connection comes back.
 */
export function useEventStream(companyId: string | undefined, onEvent: (event: Event) => void): EventStreamState {
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [lastMessageAt, setLastMessageAt] = useState<number | null>(null);

  useEffect(() => {
    if (!companyId) return;
    setStatus("connecting");
    setLastMessageAt(null);

    const source = new EventSource(api.streamUrl(companyId));

    const handleMessage = (message: MessageEvent<string>) => {
      setLastMessageAt(Date.now());
      setStatus((prev) => (prev === "reconnecting" || prev === "stale" || prev === "connecting" ? "open" : prev));
      try {
        handlerRef.current(JSON.parse(message.data) as Event);
      } catch {
        // ignore malformed frames
      }
    };
    const handleHeartbeat = () => {
      setLastMessageAt(Date.now());
      setStatus((prev) => (prev === "stale" ? "open" : prev));
    };
    source.addEventListener("commander-event", handleMessage);
    source.addEventListener("heartbeat", handleHeartbeat);
    source.addEventListener("open", () => {
      setStatus("open");
      setLastMessageAt(Date.now());
    });
    // The browser retries on its own after any drop (we never call
    // source.close() outside cleanup below), so every "error" here means
    // "reconnecting", not "gave up".
    source.addEventListener("error", () => setStatus("reconnecting"));

    const staleCheck = window.setInterval(() => {
      setLastMessageAt((last) => {
        if (last !== null && Date.now() - last > STALE_AFTER_MS) {
          setStatus((prev) => (prev === "open" ? "stale" : prev));
        }
        return last;
      });
    }, STALE_CHECK_INTERVAL_MS);

    return () => {
      window.clearInterval(staleCheck);
      source.removeEventListener("commander-event", handleMessage);
      source.removeEventListener("heartbeat", handleHeartbeat);
      source.close();
    };
  }, [companyId]);

  return { status, lastMessageAt };
}
