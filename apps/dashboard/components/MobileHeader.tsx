"use client";

import { AccountBadge } from "@/components/AccountBadge";
import { useRealtimeConnectionStatus } from "@/components/RealtimeProvider";
import { useCompany } from "@/lib/hooks";

// Compact top bar shown only below the `lg` breakpoint (§4.2 "Mobile:
// compact header ... no permanently visible wide Sidebar"). The full nav
// lives in Sidebar's drawer mode, opened from here.
export function MobileHeader({ companyId, onOpenNav }: { companyId: string; onOpenNav: () => void }) {
  const { data: company } = useCompany(companyId);
  const connectionStatus = useRealtimeConnectionStatus();

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between gap-3 border-b border-base-border bg-base-raised px-4 py-3 lg:hidden">
      <div className="flex min-w-0 items-center gap-3">
        <button
          onClick={onOpenNav}
          className="rounded-md p-1.5 text-text-muted hover:bg-base-hover hover:text-text"
          aria-label="Open navigation"
        >
          <span className="block h-0.5 w-5 bg-current" />
          <span className="mt-1 block h-0.5 w-5 bg-current" />
          <span className="mt-1 block h-0.5 w-5 bg-current" />
        </button>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-text">{company?.name ?? "Loading…"}</p>
          {(connectionStatus === "reconnecting" || connectionStatus === "stale") && (
            <p className="truncate text-[11px] font-medium text-status-amber">
              {connectionStatus === "reconnecting" ? "Reconnecting…" : "Connection stale"}
            </p>
          )}
        </div>
      </div>
      <AccountBadge />
    </header>
  );
}
