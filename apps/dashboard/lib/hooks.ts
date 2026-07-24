"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { ProfileUpdateRequest } from "./api";

export const keys = {
  companies: ["companies"] as const,
  company: (id: string) => ["company", id] as const,
  employees: (companyId: string) => ["employees", companyId] as const,
  employeeProfile: (agentId: string) => ["employeeProfile", agentId] as const,
  missions: (companyId: string) => ["missions", companyId] as const,
  mission: (taskId: string) => ["mission", taskId] as const,
  approvals: (companyId: string) => ["approvals", companyId] as const,
  approvalHistory: (companyId: string) => ["approvalHistory", companyId] as const,
  messages: (taskId: string) => ["messages", taskId] as const,
  timeline: (companyId: string) => ["timeline", companyId] as const,
  timelineFeed: (companyId: string) => ["timelineFeed", companyId] as const,
  companyCosts: (companyId: string) => ["companyCosts", companyId] as const,
  missionCosts: (taskId: string) => ["missionCosts", taskId] as const,
  models: (companyId: string) => ["models", companyId] as const,
  reports: (companyId: string) => ["reports", companyId] as const,
  report: (reportId: string) => ["report", reportId] as const,
  situation: (companyId: string) => ["situation", companyId] as const,
};

export function useCompanies() {
  return useQuery({ queryKey: keys.companies, queryFn: api.listCompanies, refetchInterval: 15_000 });
}

export function useCompany(id: string) {
  return useQuery({ queryKey: keys.company(id), queryFn: () => api.getCompany(id) });
}

export function useEmployees(companyId: string) {
  return useQuery({ queryKey: keys.employees(companyId), queryFn: () => api.listEmployees(companyId) });
}

export function useMissions(companyId: string) {
  return useQuery({ queryKey: keys.missions(companyId), queryFn: () => api.listMissions(companyId) });
}

export function useMission(taskId: string) {
  return useQuery({ queryKey: keys.mission(taskId), queryFn: () => api.getMission(taskId) });
}

export function useApprovals(companyId: string) {
  return useQuery({ queryKey: keys.approvals(companyId), queryFn: () => api.listApprovals(companyId) });
}

export function useApprovalHistory(companyId: string) {
  return useQuery({ queryKey: keys.approvalHistory(companyId), queryFn: () => api.listApprovalHistory(companyId) });
}

export function useMessages(taskId: string) {
  return useQuery({ queryKey: keys.messages(taskId), queryFn: () => api.listMessages(taskId) });
}

export function useTimeline(companyId: string) {
  return useQuery({ queryKey: keys.timeline(companyId), queryFn: () => api.getTimeline(companyId) });
}

/** Full Timeline page: cursor-paginated "load earlier" over the newest-
 * first event page(). Kept as its own infinite query (distinct cache key
 * from useTimeline's single most-recent page) since the two consumers
 * need different-shaped data. SSE-driven invalidation (invalidateForEvent)
 * refetches every already-loaded page, so an open Timeline stays live. */
export function useTimelineFeed(companyId: string) {
  return useInfiniteQuery({
    queryKey: keys.timelineFeed(companyId),
    queryFn: ({ pageParam }: { pageParam: number | undefined }) => api.getTimeline(companyId, pageParam),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });
}

export function useCompanyCosts(companyId: string) {
  return useQuery({
    queryKey: keys.companyCosts(companyId),
    queryFn: () => api.getCompanyCosts(companyId),
    refetchInterval: 15_000,
  });
}

export function useMissionCosts(taskId: string) {
  return useQuery({ queryKey: keys.missionCosts(taskId), queryFn: () => api.getMissionCosts(taskId) });
}

export function useModels(companyId: string) {
  return useQuery({ queryKey: keys.models(companyId), queryFn: () => api.listModels(companyId) });
}

export function useSetModel(companyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ role, model }: { role: string; model: string }) => api.setModel(companyId, role, model),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.models(companyId) });
      qc.invalidateQueries({ queryKey: keys.timeline(companyId) });
    },
  });
}

export function useEmployeeProfile(agentId: string) {
  return useQuery({ queryKey: keys.employeeProfile(agentId), queryFn: () => api.getEmployeeProfile(agentId) });
}

export function useUpdateEmployeeProfile(companyId: string, agentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ProfileUpdateRequest) => api.updateEmployeeProfile(agentId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.employeeProfile(agentId) });
      qc.invalidateQueries({ queryKey: keys.employees(companyId) });
    },
  });
}

export function useReports(companyId: string) {
  return useQuery({ queryKey: keys.reports(companyId), queryFn: () => api.listReports(companyId) });
}

export function useReport(reportId: string) {
  return useQuery({ queryKey: keys.report(reportId), queryFn: () => api.getReport(reportId) });
}

export function useSituation(companyId: string) {
  return useQuery({
    queryKey: keys.situation(companyId),
    queryFn: () => api.getSituation(companyId),
    refetchInterval: 60_000,
  });
}

export function useGenerateReport(companyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.generateReport(companyId),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.reports(companyId) }),
  });
}

export function useCreateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.createCompany(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.companies }),
  });
}

export function useArchiveCompany(companyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.archiveCompany(companyId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.companies });
      qc.invalidateQueries({ queryKey: keys.company(companyId) });
    },
  });
}

export function useUpdateCompanySettings(companyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name?: string; provider?: "mock" | "anthropic"; anthropic_api_key?: string }) =>
      api.updateCompanySettings(companyId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.company(companyId) });
      qc.invalidateQueries({ queryKey: keys.companies });
    },
  });
}

export function useCreateMission(companyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title: string; description: string; priority: string }) =>
      api.createMission(companyId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.missions(companyId) }),
  });
}

export function useAssignMission(companyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => api.assignMission(taskId),
    onSuccess: (task) => {
      qc.invalidateQueries({ queryKey: keys.missions(companyId) });
      qc.invalidateQueries({ queryKey: keys.mission(task.id) });
      qc.invalidateQueries({ queryKey: keys.employees(companyId) });
    },
  });
}

export function usePostMessage(taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (text: string) => api.postMessage(taskId, text),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.messages(taskId) }),
  });
}

export function useDecideApproval(companyId: string, taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      approvalId,
      decision,
      comment,
    }: {
      approvalId: string;
      decision: "approve" | "reject" | "request_changes";
      comment?: string;
    }) => api.decideApproval(approvalId, decision, comment),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.approvals(companyId) });
      qc.invalidateQueries({ queryKey: keys.approvalHistory(companyId) });
      qc.invalidateQueries({ queryKey: keys.missions(companyId) });
      qc.invalidateQueries({ queryKey: keys.mission(taskId) });
      qc.invalidateQueries({ queryKey: keys.employees(companyId) });
    },
  });
}

export function invalidateForEvent(
  qc: ReturnType<typeof useQueryClient>,
  companyId: string,
  taskId?: string | null,
  agentId?: string | null
) {
  qc.invalidateQueries({ queryKey: keys.missions(companyId) });
  qc.invalidateQueries({ queryKey: keys.employees(companyId) });
  qc.invalidateQueries({ queryKey: keys.approvals(companyId) });
  qc.invalidateQueries({ queryKey: keys.approvalHistory(companyId) });
  qc.invalidateQueries({ queryKey: keys.timeline(companyId) });
  qc.invalidateQueries({ queryKey: keys.timelineFeed(companyId) });
  qc.invalidateQueries({ queryKey: keys.companyCosts(companyId) });
  qc.invalidateQueries({ queryKey: keys.models(companyId) });
  if (taskId) {
    qc.invalidateQueries({ queryKey: keys.mission(taskId) });
    qc.invalidateQueries({ queryKey: keys.messages(taskId) });
    qc.invalidateQueries({ queryKey: keys.missionCosts(taskId) });
  }
  if (agentId) {
    qc.invalidateQueries({ queryKey: keys.employeeProfile(agentId) });
  }
}
