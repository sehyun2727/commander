"use client";

import Link from "next/link";
import type { NextAction } from "@/lib/types";
import { isKnownNextActionKind, isSafeInternalRoute, nextActionTone } from "@/lib/utils";
import type { Tone } from "@/lib/utils";

const TONE_PANEL_CLASS: Record<Tone, string> = {
  green: "border-status-green/40 bg-status-green-soft",
  amber: "border-status-amber/40 bg-status-amber-soft",
  red: "border-status-red/40 bg-status-red-soft",
  gray: "border-base-border bg-base-card",
};

const TONE_BADGE_CLASS: Record<Tone, string> = {
  green: "bg-status-green text-black",
  amber: "bg-status-amber text-black",
  red: "bg-status-red text-white",
  gray: "bg-base-hover text-text-muted",
};

// Sprint 14 §4.4: renders the server's next_action verbatim -- never
// recomputes precedence, never invents a treatment for a kind it doesn't
// recognize. Unknown kinds (a future server-added tier this build predates)
// degrade to a generic, non-crashing "attention" card with a manual refresh,
// never a guessed destructive action.
export function PrimaryActionPanel({
  nextAction,
  companyId,
  onRefresh,
}: {
  nextAction: NextAction;
  companyId: string;
  onRefresh: () => void;
}) {
  const known = isKnownNextActionKind(nextAction.kind);
  const tone: Tone = known ? nextActionTone(nextAction.kind) : "gray";
  const safeRoute = known && isSafeInternalRoute(companyId, nextAction.route) ? nextAction.route : null;

  return (
    <section className={`rounded-xl border p-5 shadow-panel ${TONE_PANEL_CLASS[tone]}`}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${TONE_BADGE_CLASS[tone]}`}>
          {known ? nextAction.urgency : "attention"}
        </span>
        {known && nextAction.requires_ceo_input && (
          <span className="text-[10px] font-medium uppercase tracking-wide text-text-faint">Needs your input</span>
        )}
      </div>
      <h2 className="text-base font-semibold text-text">
        {known ? nextAction.title : "Something needs a look"}
      </h2>
      <p className="mt-1 text-sm text-text-muted">
        {known
          ? nextAction.explanation
          : "This company has an update this Workspace doesn't recognize yet. Try refreshing, or check a specific page."}
      </p>
      <div className="mt-4">
        {safeRoute ? (
          <Link
            href={safeRoute}
            className="inline-block rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            Go there →
          </Link>
        ) : (
          <button
            onClick={onRefresh}
            className="inline-block rounded-lg border border-base-border bg-base-card px-4 py-2 text-sm font-medium text-text-muted hover:bg-base-hover"
          >
            Refresh
          </button>
        )}
      </div>
    </section>
  );
}
