import { AgentState, StatusWord as StatusWordToken, TASK_STATE_STATUS_WORD, AGENT_STATE_STATUS_WORD, TaskState } from "@/lib/types";
import type { Tone } from "@/lib/utils";
import { StatusPill } from "./StatusPill";

// The single source of external status copy (UX_SPEC §1). Every card,
// badge, kanban column, and filter renders a status through this map —
// never the raw internal TaskState/AgentState string. Add a locale here
// (not a second map) if/when Commander ships i18n.
const STATUS_WORD_LABEL: Record<StatusWordToken, string> = {
  [StatusWordToken.PLANNING]: "Planning",
  [StatusWordToken.DEVELOPING]: "Developing",
  [StatusWordToken.REVIEWING]: "Reviewing",
  [StatusWordToken.NEEDS_DECISION]: "Needs your decision",
  [StatusWordToken.BLOCKED]: "Blocked — see why",
  [StatusWordToken.COMPLETED]: "Completed",
  [StatusWordToken.FAILED]: "Failed — see report",
  [StatusWordToken.CANCELLED]: "Cancelled",
  [StatusWordToken.IDLE]: "Idle",
};

const STATUS_WORD_TONE: Record<StatusWordToken, Tone> = {
  [StatusWordToken.PLANNING]: "gray",
  [StatusWordToken.DEVELOPING]: "amber",
  [StatusWordToken.REVIEWING]: "amber",
  [StatusWordToken.NEEDS_DECISION]: "amber",
  [StatusWordToken.BLOCKED]: "red",
  [StatusWordToken.COMPLETED]: "green",
  [StatusWordToken.FAILED]: "red",
  [StatusWordToken.CANCELLED]: "red",
  [StatusWordToken.IDLE]: "gray",
};

export function taskStatusWord(state: string): StatusWordToken {
  return TASK_STATE_STATUS_WORD[state as TaskState] ?? StatusWordToken.PLANNING;
}

export function agentStatusWord(state: string): StatusWordToken {
  return AGENT_STATE_STATUS_WORD[state as AgentState] ?? StatusWordToken.IDLE;
}

// A company has many Missions but the My Companies card (UX_SPEC §3.1)
// needs one status word. Priority order is most-urgent-first: a Mission
// waiting on the CEO always wins, then anything actively stuck or
// in flight; an all-idle/no-Missions company reads as Idle.
const COMPANY_STATUS_PRIORITY: StatusWordToken[] = [
  StatusWordToken.NEEDS_DECISION,
  StatusWordToken.BLOCKED,
  StatusWordToken.REVIEWING,
  StatusWordToken.DEVELOPING,
  StatusWordToken.PLANNING,
];

export function companyStatusWord(missionStates: string[]): StatusWordToken {
  const tokens = new Set(missionStates.map(taskStatusWord));
  return COMPANY_STATUS_PRIORITY.find((token) => tokens.has(token)) ?? StatusWordToken.IDLE;
}

export function statusWordLabel(token: StatusWordToken): string {
  return STATUS_WORD_LABEL[token];
}

export function statusWordTone(token: StatusWordToken): Tone {
  return STATUS_WORD_TONE[token];
}

export function StatusWord({ token }: { token: StatusWordToken }) {
  return <StatusPill tone={statusWordTone(token)} label={statusWordLabel(token)} />;
}
