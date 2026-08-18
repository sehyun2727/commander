import Link from "next/link";
import type { PendingActions } from "@/lib/types";
import {
  pendingApprovalRoute,
  pendingClarificationRoute,
  pendingFailureRoute,
  pendingSpecificationReviewRoute,
} from "@/lib/utils";

interface PendingItem {
  key: string;
  label: string;
  reason: string;
  route: string;
}

// §4.5: concise pending items in a fixed display order that mirrors
// next_action.py's own tier order (clarification, specification_review,
// approval, failure) -- a static list order, not a recomputation of which
// single item next_action already chose as most urgent.
export function PendingAttentionList({ pending, companyId }: { pending: PendingActions; companyId: string }) {
  const items: PendingItem[] = [];

  if (pending.clarification) {
    const count = pending.clarification.questions.length;
    items.push({
      key: "clarification",
      label: "Clarification needed",
      reason: `${count} question${count === 1 ? "" : "s"} waiting on you`,
      route: pendingClarificationRoute(companyId, pending.clarification.specification_id),
    });
  }
  if (pending.specification_review) {
    items.push({
      key: "specification_review",
      label: "Specification ready for review",
      reason: `Version ${pending.specification_review.version}`,
      route: pendingSpecificationReviewRoute(companyId, pending.specification_review.specification_id),
    });
  }
  if (pending.approval) {
    items.push({
      key: "approval",
      label: "Decision needed",
      reason: pending.approval.subject,
      route: pendingApprovalRoute(companyId),
    });
  }
  if (pending.failure) {
    items.push({
      key: "failure",
      label: pending.failure.resource_type === "specification" ? "Planning needs attention" : "Mission needs attention",
      reason: pending.failure.reason ?? "No automatic next step",
      route: pendingFailureRoute(companyId, pending.failure),
    });
  }

  return (
    <section className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-faint">Pending your attention</h2>
      {items.length === 0 ? (
        <p className="text-sm text-text-faint">Nothing pending.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item.key}>
              <Link
                href={item.route}
                className="block rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm transition-colors hover:border-accent/40"
              >
                <p className="font-medium text-text">{item.label}</p>
                <p className="mt-0.5 truncate text-xs text-text-faint">{item.reason}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
