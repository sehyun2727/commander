"use client";

import Link from "next/link";
import { ErrorState } from "@/components/ErrorState";
import { useGenerateReport, useReports } from "@/lib/hooks";
import { relativeTime } from "@/lib/utils";

export default function ReportsPage({ params }: { params: { id: string } }) {
  const companyId = params.id;
  const { data: reports, isLoading, isError } = useReports(companyId);
  const generate = useGenerateReport(companyId);

  return (
    <main className="mx-auto max-w-3xl px-8 py-10">
      <header className="mb-6 flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-text">Reports</h1>
          <p className="mt-1 text-sm text-text-muted">Executive summaries of the last 24 hours, on demand.</p>
        </div>
        <button
          onClick={() => generate.mutate()}
          disabled={generate.isPending}
          className="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {generate.isPending ? "Generating…" : "Generate Report"}
        </button>
      </header>

      {isLoading ? (
        <p className="text-sm text-text-muted">Loading reports…</p>
      ) : isError ? (
        <ErrorState description="Couldn't load Reports. Try refreshing in a moment." />
      ) : !reports?.length ? (
        <p className="text-sm text-text-faint">No reports yet. Generate one to get started.</p>
      ) : (
        <div className="space-y-2">
          {reports.map((report) => (
            <Link
              key={report.id}
              href={`/company/${companyId}/reports/${report.id}`}
              className="block rounded-lg border border-base-border bg-base-card px-3 py-2 text-sm text-text-muted hover:border-accent/50 hover:text-text"
            >
              Report — {relativeTime(report.generated_at)}
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
