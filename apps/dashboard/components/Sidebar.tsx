"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRealtimeConnectionStatus } from "@/components/RealtimeProvider";
import { useCompany } from "@/lib/hooks";
import { useAuth } from "@/lib/auth-context";

export function Sidebar({
  companyId,
  mobileOpen = false,
  onClose,
}: {
  companyId: string;
  mobileOpen?: boolean;
  onClose?: () => void;
}) {
  const pathname = usePathname();
  const { data: company } = useCompany(companyId);
  const connectionStatus = useRealtimeConnectionStatus();
  const { user, logout } = useAuth();

  const links = [
    { href: `/company/${companyId}`, label: "CEO Workspace", exact: true },
    { href: `/company/${companyId}/decisions`, label: "Decisions" },
    { href: `/company/${companyId}/specifications`, label: "Specifications" },
    { href: `/company/${companyId}/missions`, label: "Missions" },
    { href: `/company/${companyId}/employees`, label: "Employees" },
    { href: `/company/${companyId}/timeline`, label: "Timeline" },
    { href: `/company/${companyId}/reports`, label: "Reports" },
    { href: `/company/${companyId}/workspace`, label: "Workspace" },
    { href: `/company/${companyId}/settings`, label: "Company Settings" },
  ];

  return (
    <>
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-72 -translate-x-full flex-col border-r border-base-border bg-base-raised transition-transform duration-200 ease-out lg:static lg:z-auto lg:h-screen lg:w-60 lg:shrink-0 lg:translate-x-0 ${
          mobileOpen ? "translate-x-0" : ""
        }`}
      >
        <div className="border-b border-base-border px-5 py-4">
          <div className="flex items-center justify-between gap-2">
            <Link href="/" className="text-xs font-medium uppercase tracking-wider text-text-faint hover:text-text-muted">
              ← All Companies
            </Link>
            <button
              onClick={onClose}
              className="rounded-md p-1 text-text-faint hover:bg-base-hover hover:text-text lg:hidden"
              aria-label="Close navigation"
            >
              ✕
            </button>
          </div>
          <p className="mt-2 truncate text-sm font-semibold text-text">{company?.name ?? "Loading…"}</p>
          {company?.provider === "mock" && (
            <span
              title="This company runs on a simulated AI provider — deliverables are deterministic placeholders, not real generation. Connect a real provider in Company Settings for genuine output."
              className="mt-1 inline-flex items-center gap-1.5 rounded bg-status-amber-soft px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-status-amber"
            >
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current" />
              Simulation mode
            </span>
          )}
          {connectionStatus === "reconnecting" && (
            <span className="mt-2 flex items-center gap-1.5 text-[11px] font-medium text-status-amber">
              <span className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-current" />
              Reconnecting…
            </span>
          )}
          {connectionStatus === "stale" && (
            <span className="mt-2 flex items-center gap-1.5 text-[11px] font-medium text-status-amber">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-current" />
              Connection stale
            </span>
          )}
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {links.map((link) => {
            const active = link.exact ? pathname === link.href : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={onClose}
                aria-current={active ? "page" : undefined}
                className={`block rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  active ? "bg-accent-soft text-accent" : "text-text-muted hover:bg-base-hover hover:text-text"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-base-border px-5 py-3">
          {user && (
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="truncate text-[11px] text-text-faint" title={user.email}>
                {user.email}
              </span>
              <button
                onClick={() => logout()}
                className="shrink-0 text-[11px] font-medium text-text-faint transition-colors hover:text-status-red"
              >
                Sign out
              </button>
            </div>
          )}
          <p className="text-[11px] text-text-faint">Commander OS</p>
        </div>
      </aside>
    </>
  );
}
