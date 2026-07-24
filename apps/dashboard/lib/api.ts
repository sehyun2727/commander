import type {
  AgentProfile,
  Approval,
  DecisionStyle,
  Event,
  ModelCatalogEntry,
  Personality,
  Project,
  ProjectCostSummary,
  Report,
  Situation,
  Starter,
  Task,
  TaskCostSummary,
  TimelinePage,
  WorkingStyle,
} from "./types";
import type { Agent } from "./types";

export interface ProfileUpdateRequest {
  personality?: Personality;
  working_style?: WorkingStyle;
  decision_style?: DecisionStyle;
  custom_instructions?: string;
  model_ref?: string | null;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status} ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  streamUrl(projectId: string) {
    return `${API_URL}/api/events/stream?project_id=${encodeURIComponent(projectId)}`;
  },

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
  getEmployeeProfile: (agentId: string) => request<AgentProfile>(`/api/agents/${agentId}/profile`),
  updateEmployeeProfile: (agentId: string, body: ProfileUpdateRequest) =>
    request<AgentProfile>(`/api/agents/${agentId}/profile`, { method: "PUT", body: JSON.stringify(body) }),

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
  listStarters: (companyId: string) => request<Starter[]>(`/api/projects/${companyId}/starters`),

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
};
