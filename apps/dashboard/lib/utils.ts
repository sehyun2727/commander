import type { Event } from "./types";

export type Tone = "green" | "amber" | "red" | "gray";

const TASK_STATE_TONE: Record<string, Tone> = {
  created: "gray",
  assigned: "amber",
  in_progress: "amber",
  in_review: "amber",
  pending_approval: "amber",
  retrying: "amber",
  completed: "green",
  failed: "red",
  cancelled: "red",
};

const AGENT_STATE_TONE: Record<string, Tone> = {
  idle: "gray",
  assigned: "amber",
  planning: "amber",
  working: "amber",
  waiting_review: "amber",
  blocked: "red",
  completed: "green",
  failed: "red",
};

const APPROVAL_STATUS_TONE: Record<string, Tone> = {
  pending: "amber",
  approved: "green",
  rejected: "red",
  changes_requested: "amber",
};

export function taskStateTone(state: string): Tone {
  return TASK_STATE_TONE[state] ?? "gray";
}

export function agentStateTone(state: string): Tone {
  return AGENT_STATE_TONE[state] ?? "gray";
}

export function approvalStatusTone(status: string): Tone {
  return APPROVAL_STATUS_TONE[status] ?? "gray";
}

const TASK_STATE_LABEL: Record<string, string> = {
  created: "New",
  assigned: "Assigned",
  in_progress: "In Progress",
  in_review: "In Audit",
  pending_approval: "Awaiting CEO Decision",
  retrying: "Reworking",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

const AGENT_STATE_LABEL: Record<string, string> = {
  idle: "Idle",
  assigned: "Assigned",
  planning: "Planning",
  working: "Working",
  waiting_review: "Handing Off",
  blocked: "Blocked",
  completed: "Wrapping Up",
  failed: "Failed",
};

const APPROVAL_STATUS_LABEL: Record<string, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  changes_requested: "Changes Requested",
};

const ROLE_LABEL: Record<string, string> = {
  pm: "PM",
  engineer: "Engineer",
  reviewer: "Reviewer",
};

export function taskStateLabel(state: string): string {
  return TASK_STATE_LABEL[state] ?? state;
}

export function agentStateLabel(state: string): string {
  return AGENT_STATE_LABEL[state] ?? state;
}

export function approvalStatusLabel(status: string): string {
  return APPROVAL_STATUS_LABEL[status] ?? status;
}

export function roleLabel(role: string): string {
  return ROLE_LABEL[role] ?? role;
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
