"use client";

import { useState } from "react";
import { useEmployees, useStartPlanning } from "@/lib/hooks";

// Sprint 12 §4.1: starting planning requires a hired CTO -- the backend
// returns 409 (CTOVacantError) otherwise. Checking role === "cto" here (not
// a hardcoded role title) keeps this Rule #16-compliant while still letting
// the CEO see *why* the button is disabled before they click it (Rule #18).
export function StartPlanningForm({ companyId }: { companyId: string }) {
  const [open, setOpen] = useState(false);
  const [requestText, setRequestText] = useState("");
  const { data: employees } = useEmployees(companyId);
  const start = useStartPlanning(companyId);
  const hasCto = (employees ?? []).some((employee) => employee.role === "cto");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!requestText.trim() || !hasCto) return;
    await start.mutateAsync({ request_text: requestText.trim() });
    setRequestText("");
    setOpen(false);
  }

  if (!open) {
    return (
      <div className="flex flex-col items-end gap-1.5">
        <button
          onClick={() => setOpen(true)}
          disabled={!hasCto}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          + Start Planning
        </button>
        {!hasCto && <p className="text-xs text-text-faint">Hire a CTO before starting a Project Specification.</p>}
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <textarea
        autoFocus
        value={requestText}
        onChange={(e) => setRequestText(e.target.value)}
        placeholder="What do you want the company to build? The PM and CTO will turn this into a Project Specification."
        rows={3}
        className="w-full resize-none rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
      />
      <div className="mt-3 flex gap-2">
        <button
          type="submit"
          disabled={start.isPending || !requestText.trim()}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {start.isPending ? "Starting…" : "Start Planning"}
        </button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="rounded-lg px-4 py-2 text-sm font-medium text-text-muted hover:text-text"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
