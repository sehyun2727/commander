"use client";

import { useMemo, useState } from "react";
import { useEmployees, useHireEmployee, useModels, useRoles, useSkillTemplates } from "@/lib/hooks";
import { registryRoleFor } from "@/lib/utils";

export function NewEmployeeForm({ companyId }: { companyId: string }) {
  const [open, setOpen] = useState(false);
  const { data: roles } = useRoles(companyId);
  const { data: employees } = useEmployees(companyId);
  const { data: models } = useModels(companyId);
  const { data: skillTemplates } = useSkillTemplates(companyId);
  const hire = useHireEmployee(companyId);

  const [roleKey, setRoleKey] = useState("");
  const [name, setName] = useState("");
  const [modelRef, setModelRef] = useState("");
  const [skillTemplateKey, setSkillTemplateKey] = useState("");

  // Sprint 11 §6.9: leadership Roles are singletons -- once occupied, they
  // stay visible (so the CEO can see the position is filled) but cannot be
  // selected again. Worker Roles never lock, regardless of headcount.
  const occupiedSingletons = useMemo(() => {
    const counts = new Map<string, number>();
    for (const employee of employees ?? []) {
      counts.set(employee.role, (counts.get(employee.role) ?? 0) + 1);
    }
    return new Set((roles ?? []).filter((role) => role.singleton && (counts.get(role.key) ?? 0) > 0).map((r) => r.key));
  }, [roles, employees]);

  const hireableRoles = (roles ?? []).filter((role) => !occupiedSingletons.has(role.key));
  const effectiveRoleKey = roleKey || hireableRoles[0]?.key || "";

  const modelEntry = models?.find((m) => m.role === registryRoleFor(roles, effectiveRoleKey));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!effectiveRoleKey || !name.trim() || occupiedSingletons.has(effectiveRoleKey)) return;
    await hire.mutateAsync({
      role_key: effectiveRoleKey,
      name: name.trim(),
      model_ref: modelRef || undefined,
      skill_template_key: skillTemplateKey || undefined,
    });
    setRoleKey("");
    setName("");
    setModelRef("");
    setSkillTemplateKey("");
    setOpen(false);
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        disabled={hireableRoles.length === 0}
        className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
      >
        + Hire Employee
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-text-faint">Role</label>
          <select
            autoFocus
            value={effectiveRoleKey}
            onChange={(e) => setRoleKey(e.target.value)}
            className="w-full rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
          >
            {(roles ?? []).map((role) => (
              <option key={role.key} value={role.key} disabled={occupiedSingletons.has(role.key)}>
                {role.title}
                {occupiedSingletons.has(role.key) ? " (already hired)" : ""}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-text-faint">Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Employee name"
            className="w-full rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
          />
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-text-faint">Model</label>
          <select
            value={modelRef}
            onChange={(e) => setModelRef(e.target.value)}
            className="w-full rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
          >
            <option value="">Use company default{modelEntry ? ` (${modelEntry.current_model})` : ""}</option>
            {(modelEntry?.options ?? []).map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-text-faint">
            Skill template
          </label>
          <select
            value={skillTemplateKey}
            onChange={(e) => setSkillTemplateKey(e.target.value)}
            className="w-full rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
          >
            <option value="">Default</option>
            {(skillTemplates ?? []).map((template) => (
              <option key={template.key} value={template.key}>
                {template.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-3 flex gap-2">
        <button
          type="submit"
          disabled={hire.isPending || !effectiveRoleKey || !name.trim()}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {hire.isPending ? "Hiring…" : "Hire"}
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
