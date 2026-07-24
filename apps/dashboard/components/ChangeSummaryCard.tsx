"use client";

import { useState } from "react";
import { useMissionDiff } from "@/lib/hooks";
import type { CodeStats } from "@/lib/types";
import { approvalStatusLabel, approvalStatusTone, parseUnifiedDiff } from "@/lib/utils";

const TONE_CLASS: Record<string, string> = {
  green: "text-status-green",
  amber: "text-status-amber",
  red: "text-status-red",
  gray: "text-text-faint",
};

function DiffHunk({ hunkText }: { hunkText: string }) {
  return (
    <pre className="max-h-80 overflow-auto rounded-lg bg-base-raised p-3 text-xs">
      {hunkText.split("\n").map((line, i) => {
        let color = "text-text-faint";
        if (line.startsWith("+") && !line.startsWith("+++")) color = "text-status-green";
        else if (line.startsWith("-") && !line.startsWith("---")) color = "text-status-red";
        return (
          <div key={i} className={color}>
            {line || " "}
          </div>
        );
      })}
    </pre>
  );
}

// Summary + stats + verdict are the landing view (UX_SPEC: diff is never
// the landing view). The diff itself is opt-in, behind "View file changes".
export function ChangeSummaryCard({
  taskId,
  summary,
  stats,
  verdict,
}: {
  taskId: string;
  summary: string;
  stats: CodeStats;
  verdict?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [openFile, setOpenFile] = useState<string | null>(null);
  const { data: diff, isLoading } = useMissionDiff(taskId, expanded);
  const files = diff ? parseUnifiedDiff(diff.diff_text) : [];

  return (
    <div className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-text">
          {stats.files_added + stats.files_modified + stats.files_deleted} file
          {stats.files_added + stats.files_modified + stats.files_deleted === 1 ? "" : "s"} changed{" "}
          <span className="text-status-green">+{stats.additions}</span>{" "}
          <span className="text-status-red">−{stats.deletions}</span>
        </p>
        {verdict && (
          <span
            className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${TONE_CLASS[approvalStatusTone(verdict)]}`}
          >
            {approvalStatusLabel(verdict)}
          </span>
        )}
      </div>

      <p className="mt-2 whitespace-pre-wrap text-sm text-text-muted">{summary}</p>

      <button
        onClick={() => setExpanded((v) => !v)}
        className="mt-3 text-xs font-medium text-accent hover:text-accent-hover"
      >
        {expanded ? "Hide file changes" : "View file changes"}
      </button>

      {expanded && (
        <div className="mt-3 space-y-2 border-t border-base-border pt-3">
          {isLoading ? (
            <p className="text-xs text-text-faint">Loading diff…</p>
          ) : files.length === 0 ? (
            <p className="text-xs text-text-faint">No diff available.</p>
          ) : (
            files.map((file) => (
              <div key={file.path}>
                <button
                  onClick={() => setOpenFile((v) => (v === file.path ? null : file.path))}
                  className="flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left text-xs hover:bg-base-hover"
                >
                  <span className="truncate font-mono text-text-muted">{file.path}</span>
                  <span className="shrink-0">
                    <span className="text-status-green">+{file.additions}</span>{" "}
                    <span className="text-status-red">−{file.deletions}</span>
                  </span>
                </button>
                {openFile === file.path && <DiffHunk hunkText={file.hunkText} />}
              </div>
            ))
          )}
          {diff?.truncated && (
            <p className="text-[11px] text-text-faint">Diff truncated — showing the first portion only.</p>
          )}
        </div>
      )}
    </div>
  );
}
