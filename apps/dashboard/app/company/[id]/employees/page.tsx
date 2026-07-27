"use client";

import { EmployeeCard } from "@/components/EmployeeCard";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { useCompanyCosts, useEmployees, useMissions } from "@/lib/hooks";

export default function EmployeesPage({ params }: { params: { id: string } }) {
  const companyId = params.id;
  const { data: employees, isLoading, isError } = useEmployees(companyId);
  const { data: missions } = useMissions(companyId);
  const { data: costs } = useCompanyCosts(companyId);
  const spendByAgent = new Map((costs?.by_agent ?? []).map((entry) => [entry.agent_id, entry.total_usd]));

  return (
    <main className="mx-auto max-w-5xl px-8 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-text">Employees</h1>
        <p className="mt-1 text-sm text-text-muted">Your Department, hired the moment this company was founded.</p>
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
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {employees?.map((employee) => (
            <EmployeeCard
              key={employee.id}
              employee={employee}
              companyId={companyId}
              currentMission={missions?.find((m) => m.id === employee.current_task_id)}
              spendUsd={spendByAgent.get(employee.id)}
            />
          ))}
        </div>
      )}
    </main>
  );
}
