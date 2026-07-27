"use client";

import { useMemo, useState } from "react";
import { ErrorState } from "@/components/ErrorState";
import { TimelineFeed } from "@/components/TimelineFeed";
import { useEmployees, useTimelineFeed } from "@/lib/hooks";
import { matchesTimelineFilter, TIMELINE_FILTERS } from "@/lib/timelineVocabulary";
import type { TimelineFilterKey } from "@/lib/timelineVocabulary";

export default function TimelinePage({ params }: { params: { id: string } }) {
  const companyId = params.id;
  const [filter, setFilter] = useState<TimelineFilterKey>("all");
  const [technical, setTechnical] = useState(false);
  const { data: employees } = useEmployees(companyId);
  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } = useTimelineFeed(companyId);

  const employeeById = useMemo(() => new Map((employees ?? []).map((e) => [e.id, e])), [employees]);
  const events = useMemo(() => data?.pages.flatMap((page) => page.items) ?? [], [data]);
  const filtered = useMemo(() => events.filter((event) => matchesTimelineFilter(event, filter)), [events, filter]);

  return (
    <main className="mx-auto max-w-3xl px-8 py-10">
      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-text">Timeline</h1>
          <p className="mt-1 text-sm text-text-muted">The company&apos;s collective memory, live.</p>
        </div>
        <button
          onClick={() => setTechnical((v) => !v)}
          className={`shrink-0 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
            technical
              ? "border-accent/50 bg-accent-soft text-accent"
              : "border-base-border text-text-faint hover:text-text-muted"
          }`}
        >
          {technical ? "Technical view" : "CEO view"}
        </button>
      </header>

      <div className="mb-6 flex gap-1 border-b border-base-border">
        {TIMELINE_FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`px-3 py-2 text-sm font-medium transition-colors ${
              filter === f.key ? "border-b-2 border-accent text-text" : "text-text-faint hover:text-text-muted"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <p className="text-sm text-text-muted">Loading Timeline…</p>
      ) : isError ? (
        <ErrorState description="Couldn't load the Timeline. Try refreshing in a moment." />
      ) : (
        <>
          <div className="rounded-xl border border-base-border bg-base-card px-4 shadow-panel">
            <TimelineFeed
              events={filtered}
              technical={technical}
              employeeById={employeeById}
              emptyLabel="Nothing here yet."
            />
          </div>

          {hasNextPage && (
            <div className="mt-4 flex justify-center">
              <button
                onClick={() => fetchNextPage()}
                disabled={isFetchingNextPage}
                className="rounded-lg border border-base-border px-4 py-2 text-sm font-medium text-text-muted hover:text-text disabled:opacity-50"
              >
                {isFetchingNextPage ? "Loading…" : "Load earlier"}
              </button>
            </div>
          )}
        </>
      )}
    </main>
  );
}
