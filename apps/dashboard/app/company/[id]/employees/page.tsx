"use client";

import { EmployeeCard } from "@/components/EmployeeCard";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { NewEmployeeForm } from "@/components/NewEmployeeForm";
import { useCompanyCosts, useEmployees, useMissions, useRoles } from "@/lib/hooks";
import type { Agent } from "@/lib/types";

// Section-heading copy for the two `RoleSpec.category` values (Sprint 10
// §19 / UX_SPEC §5.4) -- not a per-Role hardcode, since every Role's own
// title/grouping still comes from the Roles API.
const CATEGORY_LABEL: Record<string, string> = {
  leadership: "Leadership",
  worker: "Engineering",
};

const CATEGORY_ORDER = ["leadership", "worker"];

export default function EmployeesPage({ params }: { params: { id: string } }) {
  const companyId = params.id;
  const { data: employees, isLoading, isError } = useEmployees(companyId);
  const { data: roles } = useRoles(companyId);
  const { data: missions } = useMissions(companyId);
  const { data: costs } = useCompanyCosts(companyId);
  const spendByAgent = new Map((costs?.by_agent ?? []).map((entry) => [entry.agent_id, entry.total_usd]));

  const employeesByRole = new Map<string, Agent[]>();
  for (const employee of employees ?? []) {
    const bucket = employeesByRole.get(employee.role) ?? [];
    bucket.push(employee);
    employeesByRole.set(employee.role, bucket);
  }

  // Roles/Employees are grouped by category, not listed flat -- "Roles are
  // positions; Employees are people" (UX_SPEC §5.4). A category section
  // only appears once it actually holds a hired Employee (hidden means
  // absent, §10.4).
  const sections = CATEGORY_ORDER.map((category) => ({
    category,
    roles: (roles ?? []).filter((role) => role.category === category),
  })).filter((section) => section.roles.some((role) => (employeesByRole.get(role.key) ?? []).length > 0));

  return (
    <main className="mx-auto max-w-5xl px-8 py-10">
      <header className="mb-8 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-text">Employees</h1>
          <p className="mt-1 text-sm text-text-muted">Your Department, hired the moment this company was founded.</p>
        </div>
        {!isLoading && !isError && <NewEmployeeForm companyId={companyId} />}
      </header>

      {isLoading ? (
        <p className="text-sm text-text-muted">Loading employees…</p>
      ) : isError ? (
        <ErrorState description="Couldn't load your Employees. Try refreshing in a moment." />
      ) : employees?.length === 0 ? (
        <EmptyState
          title="No Employees yet"
          description="Found a company to automatically hire its founding Department."
        />
      ) : (
        <div className="space-y-8">
          {sections.map((section) => (
            <section key={section.category}>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-text-faint">
                {CATEGORY_LABEL[section.category] ?? section.category}
              </h2>
              <div className="space-y-6">
                {section.roles.map((role) => {
                  const roleEmployees = employeesByRole.get(role.key) ?? [];
                  if (roleEmployees.length === 0) return null;
                  return (
                    <div key={role.key}>
                      <p className="mb-2 text-sm font-medium text-text-muted">{role.title}</p>
                      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        {roleEmployees.map((employee) => (
                          <EmployeeCard
                            key={employee.id}
                            employee={employee}
                            companyId={companyId}
                            currentMission={missions?.find((m) => m.id === employee.current_task_id)}
                            spendUsd={spendByAgent.get(employee.id)}
                            roles={roles}
                          />
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
    </main>
  );
}
