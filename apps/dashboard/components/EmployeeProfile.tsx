"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AgentAvatar } from "@/components/AgentAvatar";
import { ErrorState } from "@/components/ErrorState";
import { useEmployeeProfile, useEmployees, useModels, useUpdateEmployeeProfile } from "@/lib/hooks";
import { DecisionStyle, Personality, WorkingStyle } from "@/lib/types";
import { decisionStyleLabel, personalityLabel, roleLabel, workingStyleLabel } from "@/lib/utils";

const CUSTOM_INSTRUCTIONS_MAX_LEN = 500;

const MODEL_ROLE_FOR_AGENT_ROLE: Record<string, string> = {
  pm: "planner",
  engineer: "builder",
  reviewer: "reviewer",
};

export function EmployeeProfile({ companyId, agentId }: { companyId: string; agentId: string }) {
  const { data: employees, isError: employeesError } = useEmployees(companyId);
  const { data: profile, isLoading, isError: profileError } = useEmployeeProfile(agentId);
  const { data: models } = useModels(companyId);
  const updateProfile = useUpdateEmployeeProfile(companyId, agentId);

  const employee = employees?.find((e) => e.id === agentId);

  const [personality, setPersonality] = useState<Personality>(Personality.PROFESSIONAL);
  const [workingStyle, setWorkingStyle] = useState<WorkingStyle>(WorkingStyle.BALANCED);
  const [decisionStyle, setDecisionStyle] = useState<DecisionStyle>(DecisionStyle.BALANCED);
  const [customInstructions, setCustomInstructions] = useState("");
  const [modelRef, setModelRef] = useState<string>("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!profile) return;
    setPersonality(profile.personality);
    setWorkingStyle(profile.working_style);
    setDecisionStyle(profile.decision_style);
    setCustomInstructions(profile.custom_instructions);
    setModelRef(profile.model_ref ?? "");
  }, [profile]);

  if (isLoading) {
    return (
      <main className="mx-auto max-w-2xl px-8 py-10">
        <p className="text-sm text-text-muted">Loading employee…</p>
      </main>
    );
  }

  if (profileError || employeesError || !profile || !employee) {
    return (
      <main className="mx-auto max-w-2xl px-8 py-10">
        <Link href={`/company/${companyId}/employees`} className="text-xs font-medium text-text-faint hover:text-text-muted">
          ← Employees
        </Link>
        <div className="mt-4">
          <ErrorState
            description={
              profileError || employeesError
                ? "Couldn't load this Employee. Try refreshing in a moment."
                : "This Employee doesn't exist, or has been removed."
            }
          />
        </div>
      </main>
    );
  }

  const modelEntry = models?.find((m) => m.role === MODEL_ROLE_FOR_AGENT_ROLE[employee.role]);
  const modelOptions = modelEntry?.options ?? [];
  const effectiveModel = profile.model_ref ?? modelEntry?.current_model;

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaved(false);
    await updateProfile.mutateAsync({
      personality,
      working_style: workingStyle,
      decision_style: decisionStyle,
      custom_instructions: customInstructions,
      model_ref: modelRef || null,
    });
    setSaved(true);
  }

  return (
    <main className="mx-auto max-w-2xl px-8 py-10">
      <Link href={`/company/${companyId}/employees`} className="text-xs font-medium text-text-faint hover:text-text-muted">
        ← Employees
      </Link>

      <header className="mt-3 mb-6 flex items-center gap-3">
        <AgentAvatar name={employee.name} color={employee.avatar_color} size={48} />
        <div>
          <h1 className="text-2xl font-semibold text-text">{employee.name}</h1>
          <p className="text-xs uppercase tracking-wide text-text-faint">
            {roleLabel(employee.role)}
            {effectiveModel ? ` · ${effectiveModel}` : ""}
          </p>
        </div>
      </header>

      <form onSubmit={handleSave} className="space-y-5 rounded-xl border border-base-border bg-base-card p-6 shadow-panel">
        <div>
          <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-text-faint">Personality</label>
          <select
            value={personality}
            onChange={(e) => setPersonality(e.target.value as Personality)}
            className="w-full rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
          >
            {Object.values(Personality).map((value) => (
              <option key={value} value={value}>
                {personalityLabel(value)}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-text-faint">Working style</label>
          <select
            value={workingStyle}
            onChange={(e) => setWorkingStyle(e.target.value as WorkingStyle)}
            className="w-full rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
          >
            {Object.values(WorkingStyle).map((value) => (
              <option key={value} value={value}>
                {workingStyleLabel(value)}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-text-faint">Decision style</label>
          <select
            value={decisionStyle}
            onChange={(e) => setDecisionStyle(e.target.value as DecisionStyle)}
            className="w-full rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
          >
            {Object.values(DecisionStyle).map((value) => (
              <option key={value} value={value}>
                {decisionStyleLabel(value)}
              </option>
            ))}
          </select>
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label className="block text-xs font-medium uppercase tracking-wide text-text-faint">
              Custom instructions
            </label>
            <span className="text-xs text-text-faint">
              {customInstructions.length}/{CUSTOM_INSTRUCTIONS_MAX_LEN}
            </span>
          </div>
          <textarea
            value={customInstructions}
            onChange={(e) => setCustomInstructions(e.target.value.slice(0, CUSTOM_INSTRUCTIONS_MAX_LEN))}
            rows={4}
            placeholder="Anything specific you want this Employee to keep in mind…"
            className="w-full resize-none rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
          />
        </div>

        {modelOptions.length > 0 && (
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-text-faint">Model override</label>
            <select
              value={modelRef}
              onChange={(e) => setModelRef(e.target.value)}
              className="w-full rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
            >
              <option value="">Use company default ({modelEntry?.current_model})</option>
              {modelOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            <p className="mt-1.5 text-xs text-text-faint">
              Overrides the company-wide model chosen for this role, for this Employee only.
            </p>
          </div>
        )}

        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={updateProfile.isPending}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {updateProfile.isPending ? "Saving…" : "Save Changes"}
          </button>
          {saved && <span className="text-xs text-status-green">Saved.</span>}
        </div>
      </form>
    </main>
  );
}
