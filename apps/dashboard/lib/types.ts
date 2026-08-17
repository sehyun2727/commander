// API response shapes. Mirrors the Pydantic response_models in apps/api —
// internal names (Project/Task/Agent/Approval) stay internal here; the UI
// layer is responsible for rendering them with Commander terminology
// (Company/Mission/Employee/CEO Decision).
export type {
  Event,
  EventPayloadMap,
  Actor,
  AgentProfile,
  CheckOutcome,
  ExecutionCompletedPayload,
} from "@commander/event-schemas";
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

import type { AgentProfile, CheckOutcome } from "@commander/event-schemas";

export interface Project {
  id: string;
  name: string;
  provider: "mock" | "anthropic";
  archived: boolean;
  created_at: string;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
}

export interface Agent {
  id: string;
  project_id: string;
  // Sprint 10 Rule #16: Roles are template-owned data, not a fixed set the
  // frontend hardcodes -- the Roles API (`Role` below) is the source of
  // truth for which keys currently exist and how to present them.
  role: string;
  name: string;
  profile: AgentProfile;
  avatar_color: string;
  state: string;
  current_task_id: string | null;
  created_at: string;
}

export interface Role {
  key: string;
  title: string;
  category: "leadership" | "worker";
  singleton: boolean;
  description: string;
  // Sprint 11 §6.4: the model_registry role this Role resolves against
  // (e.g. "planner-default") -- lets the hiring/config UI derive model
  // options without a hardcoded role->registry-role map (Rule #16).
  model_ref: string;
}

export interface SkillTemplate {
  key: string;
  title: string;
  description: string;
}

export interface CodeStats {
  commit_sha: string;
  files_added: number;
  files_modified: number;
  files_deleted: number;
  additions: number;
  deletions: number;
  summary: string;
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
  deliverable_type: "code" | "document";
  branch_name: string | null;
  code_stats: CodeStats | null;
  check_results: CheckOutcome[] | null;
  specification_id: string | null;
  created_at: string;
  updated_at: string;
}

// Sprint 12: the Project Specification lifecycle. `status` mirrors
// core.lifecycle.specification_states.SpecificationStatus verbatim —
// see components/SpecificationStatusBadge.tsx for the one place that maps
// it to CEO-facing copy/tone (same pattern as StatusWord.tsx for Missions).
export interface Specification {
  id: string;
  project_id: string;
  status:
    | "draft"
    | "planning"
    | "clarification_required"
    | "ready_for_review"
    | "approved"
    | "revision_requested"
    | "rejected"
    | "cancelled"
    | "failed";
  request_text: string;
  source_task_id: string | null;
  pm_agent_id: string | null;
  cto_agent_id: string | null;
  current_version: number;
  turn_count: number;
  clarification_questions: string[] | null;
  clarification_answers: string[] | null;
  stop_reason: string | null;
  decision_comment: string | null;
  created_at: string;
  updated_at: string;
  decided_at: string | null;
}

export interface SpecificationVersion {
  id: string;
  specification_id: string;
  version: number;
  title: string;
  problem_statement: string;
  goals: string[];
  non_goals: string[];
  requirements: string[];
  acceptance_criteria: string[];
  technical_approach: string;
  architecture_components: string[];
  data_migration_impact: string;
  security_considerations: string;
  observability_requirements: string;
  test_plan: string;
  risks: { risk: string; mitigation: string }[];
  dependencies: string[];
  assumptions: string[];
  unresolved_questions: string[];
  implementation_stages: string[];
  created_at: string;
}

export interface SpecificationTurn {
  id: string;
  specification_id: string;
  turn_index: number;
  actor_role: string;
  role_key: string | null;
  agent_id: string | null;
  kind: string;
  text: string;
  created_at: string;
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

export interface Situation {
  text: string;
  generated_at: string;
}

export interface Starter {
  title: string;
  description: string;
}

export interface WorkspaceFileEntry {
  path: string;
}

export interface WorkspaceMergeRecord {
  commit_sha: string;
  subject: string;
  merged_at: string;
}

export interface WorkspaceFileContent {
  path: string;
  content: string;
}

export interface DiffResponse {
  diff_text: string;
  truncated: boolean;
}

export interface Capability {
  execution: boolean;
  reason: string | null;
}

export interface ExecutionSettings {
  execution_available: boolean;
  reason: string | null;
  execution_enabled: boolean;
}
