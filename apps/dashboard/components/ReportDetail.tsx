"use client";

import Link from "next/link";
import { useReport, useReports } from "@/lib/hooks";
import { relativeTime } from "@/lib/utils";

export function ReportDetail({ companyId, reportId }: { companyId: string; reportId: string }) {
  const { data: report, isLoading } = useReport(reportId);
  const { data: reports } = useReports(companyId);

  if (isLoading || !report) {
    return (
      <main className="mx-auto max-w-3xl px-8 py-10">
        <p className="text-sm text-text-muted">Loading report…</p>
      </main>
    );
  }

  const otherReports = (reports ?? []).filter((r) => r.id !== reportId);

  return (
    <main className="mx-auto max-w-3xl px-8 py-10">
      <Link
        href={`/company/${companyId}/reports`}
        className="text-xs font-medium text-text-faint hover:text-text-muted"
      >
        ← Reports
      </Link>

      <header className="mt-3 mb-6">
        <h1 className="text-2xl font-semibold text-text">Daily Report</h1>
        <p className="mt-1 text-sm text-text-faint">Generated {relativeTime(report.generated_at)}</p>
      </header>

      <div className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
        <pre className="whitespace-pre-wrap font-sans text-sm text-text-muted">{report.summary_markdown}</pre>
      </div>

      {otherReports.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 text-sm font-semibold text-text">Past Reports</h2>
          <div className="space-y-2">
            {otherReports.map((r) => (
              <Link
                key={r.id}
                href={`/company/${companyId}/reports/${r.id}`}
                className="block rounded-lg border border-base-border bg-base-card px-3 py-2 text-sm text-text-muted hover:border-accent/50 hover:text-text"
              >
                Report — {relativeTime(r.generated_at)}
              </Link>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
