"use client";

import { useEffect, useState } from "react";
import { useRealtimeConnectionStatus, useRealtimeLastEventAt } from "@/components/RealtimeProvider";
import { relativeTime } from "@/lib/utils";

const STATUS_LABEL: Record<string, string> = {
  connecting: "Connecting…",
  open: "Live",
  reconnecting: "Reconnecting…",
  stale: "Connection stale",
};

const STATUS_DOT: Record<string, string> = {
  connecting: "bg-status-gray",
  open: "bg-status-green",
  reconnecting: "bg-status-amber animate-pulse",
  stale: "bg-status-amber",
};

// §4.7: the CEO must be able to distinguish live / reconnecting /
// stale-degraded / offline / last-updated at a glance. `navigator.onLine`
// is a separate browser/network fact from the SSE ConnectionStatus (a
// single dropped connection isn't "offline"), so it's tracked and shown
// independently and takes visual priority when true.
export function ConnectionStatusBar() {
  const status = useRealtimeConnectionStatus();
  const lastEventAt = useRealtimeLastEventAt();
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    setOffline(typeof navigator !== "undefined" && !navigator.onLine);
    const onOnline = () => setOffline(false);
    const onOffline = () => setOffline(true);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  const label = offline ? "Offline" : STATUS_LABEL[status];
  const dot = offline ? "bg-status-red" : STATUS_DOT[status];

  return (
    <div className="flex items-center gap-2 text-xs text-text-faint">
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
      <span>{label}</span>
      {lastEventAt !== null && <span>· Updated {relativeTime(new Date(lastEventAt).toISOString())}</span>}
    </div>
  );
}
