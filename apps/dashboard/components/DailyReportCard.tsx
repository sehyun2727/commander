"use client";

import Link from "next/link";
import { useReports, useGenerateReport } from "@/lib/hooks";
import { relativeTime } from "@/lib/utils";

export function DailyReportCard({ companyId }: { companyId: string }) {
  const { data: reports, isLoading } = useReports(companyId);
  const generate = useGenerateReport(companyId);

  const latest = reports?.[0];

  return (
    <section className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-sm font-semibold text-text">Daily Report</h2>
        <button
          onClick={() => generate.mutate()}
          disabled={generate.isPending}
          className="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {generate.isPending ? "Generating…" : "Generate Report"}
        </button>
      </div>

      {isLoading && <p className="mt-3 text-sm text-text-muted">Loading…</p>}

      {!isLoading && !latest && (
        <p className="mt-3 text-sm text-text-muted">
          No reports yet. Generate one to get an executive summary of the last 24 hours.
        </p>
      )}

      {latest && (
        <div className="mt-3">
          <p className="text-xs text-text-faint">Generated {relativeTime(latest.generated_at)}</p>
          <pre className="mt-2 line-clamp-4 whitespace-pre-wrap font-sans text-sm text-text-muted">
            {latest.summary_markdown}
          </pre>
          <Link
            href={`/company/${companyId}/reports/${latest.id}`}
            className="mt-2 inline-block text-xs font-medium text-accent hover:underline"
          >
            View Full Report →
          </Link>
        </div>
      )}
    </section>
  );
}
