import type { AgentProfile, CheckOutcome, Event } from "./types";

export type Tone = "green" | "amber" | "red" | "gray";

// Task/Agent status copy and tone are owned by components/StatusWord.tsx
// (UX_SPEC §1's single vocabulary source) — not here. Approval status is a
// separate, smaller vocabulary (pending/approved/rejected/changes_requested)
// that doesn't map onto TaskState/AgentState, so it keeps its own table.
const APPROVAL_STATUS_TONE: Record<string, Tone> = {
  pending: "amber",
  approved: "green",
  rejected: "red",
  changes_requested: "amber",
};

export function approvalStatusTone(status: string): Tone {
  return APPROVAL_STATUS_TONE[status] ?? "gray";
}

const APPROVAL_STATUS_LABEL: Record<string, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  changes_requested: "Changes Requested",
};

export function approvalStatusLabel(status: string): string {
  return APPROVAL_STATUS_LABEL[status] ?? status;
}

// Sprint 10 Rule #16: a Role's display title is template-owned data (the
// Roles API's `title` field), not a frontend-hardcoded lookup -- callers
// pass in the `Role[]` they already fetched via `useRoles`.
export function roleLabel(roles: { key: string; title: string }[] | undefined, roleKey: string): string {
  return roles?.find((role) => role.key === roleKey)?.title ?? roleKey;
}

// Sprint 11 §6.4: the model_registry role ("planner"/"builder"/"reviewer"/…)
// a Role resolves against, derived from `Role.model_ref` (e.g.
// "planner-default" -> "planner") instead of a frontend-hardcoded
// role-key -> registry-role map (Rule #16).
export function registryRoleFor(
  roles: { key: string; model_ref: string }[] | undefined,
  roleKey: string
): string | undefined {
  const modelRef = roles?.find((role) => role.key === roleKey)?.model_ref;
  return modelRef?.replace(/-default$/, "");
}

const PERSONALITY_LABEL: Record<string, string> = {
  professional: "Professional",
  friendly: "Friendly",
  direct: "Direct",
  conservative: "Conservative",
};

const WORKING_STYLE_LABEL: Record<string, string> = {
  fast: "Fast-paced",
  balanced: "Balanced",
  detail_oriented: "Detail-oriented",
};

const DECISION_STYLE_LABEL: Record<string, string> = {
  risk_avoiding: "Risk-avoiding",
  balanced: "Balanced",
  experimental: "Experimental",
};

export function personalityLabel(value: string): string {
  return PERSONALITY_LABEL[value] ?? value;
}

export function workingStyleLabel(value: string): string {
  return WORKING_STYLE_LABEL[value] ?? value;
}

export function decisionStyleLabel(value: string): string {
  return DECISION_STYLE_LABEL[value] ?? value;
}

export function styleSummary(profile: AgentProfile): string {
  return `${personalityLabel(profile.personality)} · ${workingStyleLabel(profile.working_style)} · ${decisionStyleLabel(profile.decision_style)}`;
}

export function initials(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function narrate(event: Event): string {
  if (event.reason) return event.reason;
  if (event.type === "conversation.message") {
    const text = (event.payload as { text?: string }).text ?? "";
    return text.length > 140 ? `${text.slice(0, 140)}…` : text;
  }
  return event.type;
}

export function formatUsd(amount: number): string {
  // Mock-mode "play money" costs are fractions of a cent per call — a flat
  // toFixed(2) would show $0.00 for a while after every mission and make
  // Payroll look frozen even though it's accruing. Show more precision
  // below a cent so the CEO can see it move.
  if (amount === 0) return "$0.00";
  if (amount < 0.01) return `$${amount.toFixed(4)}`;
  return `$${amount.toFixed(2)}`;
}

export interface DiffFile {
  path: string;
  additions: number;
  deletions: number;
  hunkText: string;
}

// Parses `git diff`'s unified format into per-file hunks so the Workspace
// view can show a per-file stat list without a dedicated backend endpoint
// -- diff() already returns the full text, this just slices it client-side.
export function parseUnifiedDiff(diffText: string): DiffFile[] {
  if (!diffText) return [];
  const chunks = diffText.split(/(?=^diff --git )/m).filter((chunk) => chunk.startsWith("diff --git "));
  return chunks.map((chunk) => {
    const headerMatch = chunk.match(/^diff --git a\/(.+?) b\/(.+)$/m);
    const path = headerMatch ? headerMatch[2] : "unknown file";
    let additions = 0;
    let deletions = 0;
    for (const line of chunk.split("\n")) {
      if (line.startsWith("+++") || line.startsWith("---")) continue;
      if (line.startsWith("+")) additions++;
      else if (line.startsWith("-")) deletions++;
    }
    return { path, additions, deletions, hunkText: chunk };
  });
}

// CEO-facing copy per UX_SPEC: plain verdicts ("All 3 checks passed" / "1
// of 3 checks failed"), never raw output at L1 -- output tails are opt-in
// (ExecutionResults/Timeline technical rows), never shown here.
export function checksSummary(results: CheckOutcome[]): { label: string; tone: Tone } {
  const total = results.length;
  const passed = results.filter((r) => r.status === "passed").length;
  const failed = results.filter((r) => r.status === "failed").length;
  const couldNotRun = total - passed - failed;
  if (couldNotRun === total) return { label: "Checks could not run", tone: "gray" };
  if (failed > 0) return { label: `${failed} of ${total} check${total === 1 ? "" : "s"} failed`, tone: "red" };
  if (passed === total) return { label: total === 1 ? "Check passed" : `All ${total} checks passed`, tone: "green" };
  return { label: `${passed} of ${total} checks passed`, tone: "amber" };
}

export function relativeTime(iso: string): string {
  const then = new Date(iso.endsWith("Z") ? iso : `${iso}Z`).getTime();
  const diffMs = Date.now() - then;
  const seconds = Math.max(0, Math.floor(diffMs / 1000));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
