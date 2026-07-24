"use client";

import { useState } from "react";
import { StatusPill } from "@/components/StatusPill";
import type { CheckOutcome } from "@/lib/types";
import type { Tone } from "@/lib/utils";
import { checksSummary } from "@/lib/utils";

const TONE_FOR_STATUS: Record<CheckOutcome["status"], Tone> = {
  passed: "green",
  failed: "red",
  could_not_run: "gray",
};

// Output tail is disclosure level 2 (UX_SPEC): collapsed by default,
// one click away, never dumped alongside the pass/fail chip.
function CheckRow({ check }: { check: CheckOutcome }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border-b border-base-border/60 py-2 last:border-none">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 text-left"
      >
        <StatusPill tone={TONE_FOR_STATUS[check.status]} label={check.name} />
        <span className="shrink-0 text-[11px] text-text-faint">{check.duration_seconds.toFixed(1)}s</span>
      </button>
      {open && (
        <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-base-raised p-3 text-xs text-text-muted">
          {check.output || "(no output)"}
        </pre>
      )}
    </div>
  );
}

export function ExecutionResults({ results }: { results: CheckOutcome[] }) {
  const { label, tone } = checksSummary(results);
  return (
    <div className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-text">Automated Checks</p>
        <StatusPill tone={tone} label={label} />
      </div>
      <div className="mt-3">
        {results.map((check) => (
          <CheckRow key={check.name} check={check} />
        ))}
      </div>
    </div>
  );
}
