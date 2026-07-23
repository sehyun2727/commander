"use client";

import Link from "next/link";
import { useState } from "react";
import { useDecideApproval } from "@/lib/hooks";
import type { Approval } from "@/lib/types";

export function ApprovalCard({
  approval,
  companyId,
  missionTitle,
  linkToMission = true,
}: {
  approval: Approval;
  companyId: string;
  missionTitle: string;
  linkToMission?: boolean;
}) {
  const [comment, setComment] = useState("");
  const decide = useDecideApproval(companyId, approval.task_id);

  function handle(decision: "approve" | "reject" | "request_changes") {
    decide.mutate({ approvalId: approval.id, decision, comment });
  }

  return (
    <div className="rounded-xl border border-accent/30 bg-accent-soft/40 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-accent">CEO Decision needed</p>
          {linkToMission ? (
            <Link href={`/company/${companyId}/missions/${approval.task_id}`} className="text-sm font-medium text-text hover:underline">
              {missionTitle}
            </Link>
          ) : (
            <p className="text-sm font-medium text-text">{missionTitle}</p>
          )}
        </div>
      </div>

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
    </div>
  );
}
