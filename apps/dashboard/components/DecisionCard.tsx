"use client";

import Link from "next/link";
import { useState } from "react";
import { AgentAvatar } from "@/components/AgentAvatar";
import { useDecideApproval } from "@/lib/hooks";
import type { Approval } from "@/lib/types";
import { relativeTime } from "@/lib/utils";

const DECISION_LABEL: Record<string, string> = {
  approved: "Approved",
  rejected: "Rejected",
  changes_requested: "Changes requested",
};

const DECISION_TONE_CLASS: Record<string, string> = {
  approved: "text-status-green",
  rejected: "text-status-red",
  changes_requested: "text-status-amber",
};

const DEFAULT_REVIEWER_COLOR = "#64748b";

function Section({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-faint">{label}</p>
      <p className="mt-1 text-sm text-text-muted">{value}</p>
    </div>
  );
}

// Fixed anatomy per UX_SPEC §3.6: Problem / Recommendation (with reviewer
// attribution) / Risk / Impact, then Approve / Request changes / Reject.
// Sections are best-effort (workflow_engine.parsing is lenient) — any
// subset may be missing, and very old/unparseable audits have none at
// all, so this always falls back to raw_summary rather than rendering
// blank space. The same component renders both a live decision (pending)
// and a read-only history entry (decided) — one anatomy, two placements
// (Headquarters strip and the Decisions page) per item 3.5.
export function DecisionCard({
  approval,
  companyId,
  missionTitle,
  reviewerColor = DEFAULT_REVIEWER_COLOR,
  linkToMission = true,
  outcome,
}: {
  approval: Approval;
  companyId: string;
  missionTitle: string;
  reviewerColor?: string;
  linkToMission?: boolean;
  outcome?: string;
}) {
  const [comment, setComment] = useState("");
  const decide = useDecideApproval(companyId, approval.task_id);
  const isPending = approval.status === "pending";
  const { problem, recommendation, risk, impact } = approval.sections;
  const hasSections = Boolean(problem || recommendation || risk || impact);

  function handle(decision: "approve" | "reject" | "request_changes") {
    decide.mutate({ approvalId: approval.id, decision, comment });
  }

  return (
    <div
      className={`rounded-xl border p-4 ${
        isPending ? "border-accent/30 bg-accent-soft/40" : "border-base-border bg-base-card"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p
            className={`text-[11px] font-semibold uppercase tracking-wide ${
              isPending ? "text-accent" : DECISION_TONE_CLASS[approval.status] ?? "text-text-faint"
            }`}
          >
            {isPending ? "CEO Decision needed" : DECISION_LABEL[approval.status] ?? approval.status}
          </p>
          {linkToMission ? (
            <Link
              href={`/company/${companyId}/missions/${approval.task_id}`}
              className="text-sm font-medium text-text hover:underline"
            >
              {missionTitle}
            </Link>
          ) : (
            <p className="text-sm font-medium text-text">{missionTitle}</p>
          )}
        </div>
        {!isPending && (
          <span className="shrink-0 text-[11px] text-text-faint">
            {relativeTime(approval.decided_at ?? approval.created_at)}
          </span>
        )}
      </div>

      <div className="mt-3 space-y-3">
        {hasSections ? (
          <>
            <Section label="Problem" value={problem} />
            {recommendation && (
              <div>
                <div className="flex items-center gap-2">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-faint">Recommendation</p>
                  {approval.reviewer_name && (
                    <span className="flex items-center gap-1.5 text-[11px] text-text-faint">
                      <AgentAvatar name={approval.reviewer_name} color={reviewerColor} size={18} />
                      {approval.reviewer_name}
                    </span>
                  )}
                </div>
                <p className="mt-1 text-sm text-text-muted">{recommendation}</p>
              </div>
            )}
            <Section label="Risk" value={risk} />
            <Section label="Impact" value={impact} />
          </>
        ) : (
          approval.raw_summary && (
            <p className="whitespace-pre-wrap text-sm text-text-muted">{approval.raw_summary}</p>
          )
        )}
      </div>

      {isPending ? (
        <>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Optional comment for the Department…"
            rows={2}
            className="mt-3 w-full resize-none rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
          />
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              onClick={() => handle("approve")}
              disabled={decide.isPending}
              className="rounded-lg bg-status-green px-3 py-1.5 text-xs font-semibold text-black transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              Approve
            </button>
            <button
              onClick={() => handle("request_changes")}
              disabled={decide.isPending}
              className="rounded-lg border border-status-amber/50 bg-status-amber-soft px-3 py-1.5 text-xs font-semibold text-status-amber transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              Request Changes
            </button>
            <button
              onClick={() => handle("reject")}
              disabled={decide.isPending}
              className="rounded-lg border border-status-red/50 bg-status-red-soft px-3 py-1.5 text-xs font-semibold text-status-red transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              Reject
            </button>
          </div>
        </>
      ) : (
        (approval.comment || outcome) && (
          <div className="mt-3 space-y-1 border-t border-base-border pt-3 text-xs">
            {approval.comment && <p className="text-text-muted">&ldquo;{approval.comment}&rdquo;</p>}
            {outcome && <p className="text-text-faint">{outcome}</p>}
          </div>
        )
      )}
    </div>
  );
}
