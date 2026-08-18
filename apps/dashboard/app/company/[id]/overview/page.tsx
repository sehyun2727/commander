"use client";

import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { useWorkspaceOverview } from "@/lib/hooks";
import type { Tone } from "@/lib/utils";
import { relativeTime } from "@/lib/utils";

// Sprint 13 Phase 4: a minimal, additive proof that the CEO Workspace
// snapshot contract (schema + next_action policy + cursor) actually renders
// end to end. This is NOT the final CEO Workspace shell (that's Sprint 14 --
// PM conversation + Widget Dock per docs/design/UX_SPEC.md §3); it exists
// only so this sprint's backend contract has a real, running consumer. Every
// value shown here is copied straight from the snapshot response -- this
// page must never recompute next_action's precedence itself (§10).

const URGENCY_TONE: Record<string, Tone> = {
  low: "gray",
  normal: "gray",
  high: "amber",
  critical: "red",
};

const URGENCY_CLASS: Record<Tone, string> = {
  gray: "bg-base-hover text-text-muted",
  amber: "bg-status-amber-soft text-status-amber",
  red: "bg-status-red-soft text-status-red",
  green: "bg-status-green-soft text-status-green",
};

export default function WorkspaceOverviewProofPage({ params }: { params: { id: string } }) {
  const companyId = params.id;
  const { data: snapshot, isLoading, isError } = useWorkspaceOverview(companyId);

  if (isLoading) {
    return (
      <main className="mx-auto max-w-4xl px-8 py-10">
        <Header />
        <p className="text-sm text-text-muted">Loading workspace snapshot…</p>
      </main>
    );
  }

  if (isError || !snapshot) {
    return (
      <main className="mx-auto max-w-4xl px-8 py-10">
        <Header />
        <ErrorState description="Couldn't load the CEO Workspace snapshot. Try refreshing in a moment." />
      </main>
    );
  }

  const { next_action, pending_actions, organization, planning, missions, recent_activity } = snapshot;
  const tone = URGENCY_TONE[next_action.urgency] ?? "gray";
  const pendingCount = Object.values(pending_actions).filter(Boolean).length;

  return (
    <main className="mx-auto max-w-4xl px-8 py-10">
      <Header />

      <section className="mb-8 rounded-xl border border-base-border bg-base-card p-5 shadow-panel">
        <div className="mb-2 flex items-center gap-2">
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${URGENCY_CLASS[tone]}`}>
            {next_action.urgency}
          </span>
          <h2 className="text-sm font-semibold text-text">{next_action.title}</h2>
        </div>
        <p className="text-sm text-text-muted">{next_action.explanation}</p>
        {next_action.route && (
          <Link
            href={next_action.route}
            className="mt-3 inline-block rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover"
          >
            Go there →
          </Link>
        )}
      </section>

      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-4">
        <SummaryCard label="Pending actions" value={pendingCount} />
        <SummaryCard label="Employees" value={organization.counts.total} sub={`${organization.counts.busy} busy`} />
        <SummaryCard label="Active missions" value={missions.active.length} />
        <SummaryCard
          label="Planning"
          value={planning.active ? planning.status ?? "active" : "none"}
        />
      </div>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold text-text">Leadership</h2>
        <div className="space-y-2">
          {organization.leadership.map((slot) => (
            <div
              key={slot.role_key}
              className="flex items-center justify-between rounded-lg border border-base-border bg-base-card px-3 py-2 text-sm"
            >
              <span className="text-text-muted">{slot.title}</span>
              <span className={slot.occupied ? "text-text" : "text-status-amber"}>
                {slot.occupied ? slot.employee_name : "Vacant"}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="mb-8">
        <h2 className="mb-3 text-sm font-semibold text-text">Recent activity</h2>
        {recent_activity.length === 0 ? (
          <EmptyState title="No activity yet" description="Nothing has happened in this Company yet." />
        ) : (
          <div className="space-y-2">
            {recent_activity.map((item) => (
              <div key={item.id} className="rounded-lg border border-base-border bg-base-card px-3 py-2 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-text-muted">
                    {item.actor_name} · {item.kind}
                  </span>
                  <span className="shrink-0 text-xs text-text-faint">{relativeTime(item.created_at)}</span>
                </div>
                {item.reason && <p className="mt-1 text-xs text-text-faint">{item.reason}</p>}
              </div>
            ))}
          </div>
        )}
      </section>

      <p className="text-xs text-text-faint">Event cursor: {snapshot.event_cursor}</p>
    </main>
  );
}

function Header() {
  return (
    <header className="mb-8">
      <h1 className="text-2xl font-semibold text-text">Workspace Overview (Preview)</h1>
      <p className="mt-1 text-sm text-text-muted">
        A read-only preview of the CEO Workspace snapshot contract. The full CEO Workspace ships in a later sprint.
      </p>
    </header>
  );
}

function SummaryCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <p className="text-xs uppercase tracking-wide text-text-faint">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-text">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-text-faint">{sub}</p>}
    </div>
  );
}
