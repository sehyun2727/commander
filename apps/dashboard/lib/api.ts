import type {
  AgentProfile,
  Approval,
  Capability,
  DecisionStyle,
  DiffResponse,
  Event,
  ExecutionSettings,
  ModelCatalogEntry,
  Personality,
  Project,
  ProjectCostSummary,
  Report,
  Role,
  Situation,
  SkillTemplate,
  Specification,
  SpecificationTurn,
  SpecificationVersion,
  Starter,
  Task,
  TaskCostSummary,
  TimelinePage,
  User,
  WorkingStyle,
  WidgetDefinition,
  WorkspaceFileContent,
  WorkspaceFileEntry,
  WorkspaceMergeRecord,
  WorkspacePreferences,
  WorkspaceSnapshot,
  WidgetPreferenceEntry,
} from "./types";
import type { Agent } from "./types";

export interface ProfileUpdateRequest {
  personality?: Personality;
  working_style?: WorkingStyle;
  decision_style?: DecisionStyle;
  custom_instructions?: string;
  model_ref?: string | null;
  skill_template_key?: string;
}

export interface HireEmployeeRequest {
  role_key: string;
  name: string;
  model_ref?: string | null;
  skill_template_key?: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Carries the HTTP status so callers (esp. the login/register forms, which
 * need FastAPI's `detail` string verbatim -- e.g. the unified login-failure
 * message) can distinguish a 401 from a 409 from a network failure, and so
 * `request()` can tell a stale-session 401 apart from any other error. */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
    // HttpOnly session cookie (Sprint 9 §2.1) -- every request carries it,
    // never a token the frontend stores or reads itself.
    credentials: "include",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    let detail = body;
    try {
      const parsed = JSON.parse(body) as { detail?: string };
      if (parsed?.detail) detail = parsed.detail;
    } catch {
      // body wasn't JSON -- fall back to the raw text above.
    }
    if (res.status === 401 && typeof window !== "undefined") {
      // Decoupled from AuthProvider on purpose -- this module has no
      // React/router dependency. AuthProvider listens for this and clears
      // local state + redirects to /login, covering every request in the
      // app (not just the ones a page explicitly guards).
      window.dispatchEvent(new Event("commander:unauthorized"));
    }
    throw new ApiError(res.status, detail || `${init?.method ?? "GET"} ${path} failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  streamUrl(projectId: string) {
    return `${API_URL}/api/events/stream?project_id=${encodeURIComponent(projectId)}`;
  },

  // Ops
  getHealth: () => request<{ status: string }>("/api/health"),

  // Auth
  getMe: () => request<User>("/api/auth/me"),
  register: (email: string, password: string, display_name: string) =>
    request<User>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name }),
    }),
  login: (email: string, password: string) =>
    request<User>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => request<{ status: string }>("/api/auth/logout", { method: "POST" }),

  // Companies
  listCompanies: () => request<Project[]>("/api/projects"),
  getCompany: (id: string) => request<Project>(`/api/projects/${id}`),
  createCompany: (name: string) =>
    request<Project>("/api/projects", { method: "POST", body: JSON.stringify({ name }) }),
  archiveCompany: (id: string) => request<Project>(`/api/projects/${id}/archive`, { method: "POST" }),
  updateCompanySettings: (
    id: string,
    body: { name?: string; provider?: "mock" | "anthropic"; anthropic_api_key?: string }
  ) => request<Project>(`/api/projects/${id}/settings`, { method: "PATCH", body: JSON.stringify(body) }),

  // Employees
  listEmployees: (companyId: string) => request<Agent[]>(`/api/projects/${companyId}/agents`),
  hireEmployee: (companyId: string, body: HireEmployeeRequest) =>
    request<Agent>(`/api/projects/${companyId}/agents`, { method: "POST", body: JSON.stringify(body) }),
  getEmployeeProfile: (agentId: string) => request<AgentProfile>(`/api/agents/${agentId}/profile`),
  updateEmployeeProfile: (agentId: string, body: ProfileUpdateRequest) =>
    request<AgentProfile>(`/api/agents/${agentId}/profile`, { method: "PUT", body: JSON.stringify(body) }),

  // Skill Templates (Sprint 11 §6.3) — static, server-owned catalog.
  listSkillTemplates: (companyId: string) =>
    request<SkillTemplate[]>(`/api/projects/${companyId}/skill-templates`),

  // Missions
  listMissions: (companyId: string) => request<Task[]>(`/api/projects/${companyId}/tasks`),
  getMission: (taskId: string) => request<Task>(`/api/tasks/${taskId}`),
  createMission: (
    companyId: string,
    body: { title: string; description: string; priority: string; deliverable_type?: string },
  ) => request<Task>(`/api/projects/${companyId}/tasks`, { method: "POST", body: JSON.stringify(body) }),
  assignMission: (taskId: string, agentId?: string) =>
    request<Task>(`/api/tasks/${taskId}/assign`, {
      method: "POST",
      body: JSON.stringify({ agent_id: agentId ?? null }),
    }),
  cancelMission: (taskId: string, reason?: string) =>
    request<Task>(`/api/tasks/${taskId}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? null }),
    }),
  listStarters: (companyId: string) => request<Starter[]>(`/api/projects/${companyId}/starters`),

  // Roles (Sprint 10 §18) — read-only Role positions; no write route.
  listRoles: (companyId: string) => request<Role[]>(`/api/projects/${companyId}/roles`),

  // Meetings (Mission-scoped chat)
  listMessages: (taskId: string) => request<Event[]>(`/api/tasks/${taskId}/messages`),
  postMessage: (taskId: string, text: string) =>
    request<Event>(`/api/tasks/${taskId}/messages`, { method: "POST", body: JSON.stringify({ text }) }),

  // CEO Decisions
  listApprovals: (companyId: string) => request<Approval[]>(`/api/approvals?project_id=${companyId}`),
  listApprovalHistory: (companyId: string) => request<Approval[]>(`/api/approvals/history?project_id=${companyId}`),
  decideApproval: (approvalId: string, decision: "approve" | "reject" | "request_changes", comment?: string) =>
    request<Approval>(`/api/approvals/${approvalId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, comment: comment || null }),
    }),

  // Timeline
  getTimeline: (companyId: string, cursor?: number) =>
    request<TimelinePage>(
      `/api/projects/${companyId}/events${cursor != null ? `?cursor=${cursor}` : ""}`
    ),

  // Payroll
  getCompanyCosts: (companyId: string) => request<ProjectCostSummary>(`/api/projects/${companyId}/costs`),
  getMissionCosts: (taskId: string) => request<TaskCostSummary>(`/api/tasks/${taskId}/costs`),

  // Employee Models
  listModels: (companyId: string) => request<ModelCatalogEntry[]>(`/api/projects/${companyId}/models`),
  setModel: (companyId: string, role: string, model: string) =>
    request<ModelCatalogEntry>(`/api/projects/${companyId}/models/${role}`, {
      method: "PUT",
      body: JSON.stringify({ model }),
    }),

  // Daily Report
  listReports: (companyId: string) => request<Report[]>(`/api/projects/${companyId}/reports`),
  getReport: (reportId: string) => request<Report>(`/api/reports/${reportId}`),
  generateReport: (companyId: string) =>
    request<Report>(`/api/projects/${companyId}/reports/generate`, { method: "POST" }),

  // Situation Report
  getSituation: (companyId: string) => request<Situation>(`/api/projects/${companyId}/situation`),

  // Workspace
  getWorkspaceTree: (companyId: string, ref = "main") =>
    request<WorkspaceFileEntry[]>(`/api/projects/${companyId}/workspace/tree?ref=${encodeURIComponent(ref)}`),
  getWorkspaceFile: (companyId: string, path: string, ref = "main") =>
    request<WorkspaceFileContent>(
      `/api/projects/${companyId}/workspace/file?path=${encodeURIComponent(path)}&ref=${encodeURIComponent(ref)}`
    ),
  getWorkspaceMerges: (companyId: string, limit = 10) =>
    request<WorkspaceMergeRecord[]>(`/api/projects/${companyId}/workspace/merges?limit=${limit}`),
  getMissionDiff: (taskId: string) => request<DiffResponse>(`/api/tasks/${taskId}/diff`),

  // Project Specifications (Sprint 12) — PM<->CTO planning
  listSpecifications: (companyId: string) => request<Specification[]>(`/api/projects/${companyId}/specifications`),
  getSpecification: (specId: string) => request<Specification>(`/api/specifications/${specId}`),
  startPlanning: (companyId: string, body: { request_text: string; source_task_id?: string | null }) =>
    request<Specification>(`/api/projects/${companyId}/specifications`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listSpecificationTurns: (specId: string) =>
    request<SpecificationTurn[]>(`/api/specifications/${specId}/turns`),
  listSpecificationVersions: (specId: string) =>
    request<SpecificationVersion[]>(`/api/specifications/${specId}/versions`),
  answerClarification: (specId: string, answers: string[]) =>
    request<Specification>(`/api/specifications/${specId}/clarification-answer`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),
  submitSpecificationRevision: (specId: string, feedback: string) =>
    request<Specification>(`/api/specifications/${specId}/revision`, {
      method: "POST",
      body: JSON.stringify({ feedback }),
    }),
  approveSpecification: (specId: string) =>
    request<Specification>(`/api/specifications/${specId}/approve`, { method: "POST" }),
  rejectSpecification: (specId: string, reason?: string) =>
    request<Specification>(`/api/specifications/${specId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? null }),
    }),
  cancelSpecification: (specId: string, reason?: string) =>
    request<Specification>(`/api/specifications/${specId}/cancel`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? null }),
    }),
  beginExecution: (specId: string) =>
    request<Task>(`/api/specifications/${specId}/begin-execution`, { method: "POST" }),

  // CEO Workspace snapshot (Sprint 13) -- read-only, no query params beyond
  // companyId (app/modules/workspace_overview/routes.py has no pagination
  // surface); incremental updates come from the existing SSE stream, not a
  // new endpoint (DECISIONS.md #217).
  getWorkspaceOverview: (companyId: string) =>
    request<WorkspaceSnapshot>(`/api/projects/${companyId}/workspace/overview`),

  // CEO Workspace widget system (Sprint 15) -- the registry is a static,
  // server-owned catalog; preferences are per-(CEO, company) layout state
  // guarded by an optimistic-concurrency `revision` (app/modules/
  // workspace_widgets/routes.py).
  listWorkspaceWidgets: (companyId: string) =>
    request<WidgetDefinition[]>(`/api/projects/${companyId}/workspace/widgets`),
  getWorkspacePreferences: (companyId: string) =>
    request<WorkspacePreferences>(`/api/projects/${companyId}/workspace/preferences`),
  updateWorkspacePreferences: (
    companyId: string,
    body: { expected_revision: number; widgets: WidgetPreferenceEntry[] }
  ) =>
    request<WorkspacePreferences>(`/api/projects/${companyId}/workspace/preferences`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  resetWorkspacePreferences: (companyId: string) =>
    request<WorkspacePreferences>(`/api/projects/${companyId}/workspace/preferences/reset`, {
      method: "POST",
    }),

  // Execution Sandbox
  getCapabilities: () => request<Capability>("/api/system/capabilities"),
  getExecutionSettings: (companyId: string) =>
    request<ExecutionSettings>(`/api/projects/${companyId}/execution-settings`),
  setExecutionEnabled: (companyId: string, enabled: boolean) =>
    request<ExecutionSettings>(`/api/projects/${companyId}/execution-settings`, {
      method: "PUT",
      body: JSON.stringify({ enabled }),
    }),
};
