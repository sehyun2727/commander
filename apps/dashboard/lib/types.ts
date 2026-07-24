// API response shapes. Mirrors the Pydantic response_models in apps/api —
// internal names (Project/Task/Agent/Approval) stay internal here; the UI
// layer is responsible for rendering them with Commander terminology
// (Company/Mission/Employee/CEO Decision).
export type { Event, EventPayloadMap, Actor, AgentProfile } from "@commander/event-schemas";
export {
  EventType,
  AgentState,
  TaskState,
  Personality,
  WorkingStyle,
  DecisionStyle,
  StatusWord,
  TASK_STATE_STATUS_WORD,
  AGENT_STATE_STATUS_WORD,
} from "@commander/event-schemas";

import type { AgentProfile } from "@commander/event-schemas";

export interface Project {
  id: string;
  name: string;
  provider: "mock" | "anthropic";
  archived: boolean;
  created_at: string;
}

export interface Agent {
  id: string;
  project_id: string;
  role: "pm" | "engineer" | "reviewer";
  name: string;
  profile: AgentProfile;
  avatar_color: string;
  state: string;
  current_task_id: string | null;
  created_at: string;
}

export interface Task {
  id: string;
  project_id: string;
  title: string;
  description: string;
  priority: string;
  state: string;
  attempt: number;
  result_markdown: string;
  created_at: string;
  updated_at: string;
}

export interface Approval {
  id: string;
  project_id: string;
  task_id: string;
  subject: string;
  status: "pending" | "approved" | "rejected" | "changes_requested";
  comment: string | null;
  reviewer_agent_id: string | null;
  reviewer_name: string | null;
  sections: Record<string, string>;
  raw_summary: string;
  created_at: string;
  decided_at: string | null;
}

export interface TimelinePage {
  items: import("@commander/event-schemas").Event[];
  next_cursor: number | null;
}

export interface AgentCostEntry {
  agent_id: string;
  total_usd: number;
}

export interface ProjectCostSummary {
  project_id: string;
  month_total_usd: number;
  by_agent: AgentCostEntry[];
}

export interface TaskCostSummary {
  task_id: string;
  total_usd: number;
}

export interface ModelCatalogEntry {
  role: "planner" | "builder" | "reviewer";
  current_model: string;
  recommended_model: string;
  options: string[];
}

export interface Report {
  id: string;
  project_id: string;
  period_start: string;
  period_end: string;
  summary_markdown: string;
  generated_at: string;
}
