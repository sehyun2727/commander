"use client";

import { EmployeeCard } from "@/components/EmployeeCard";
import { useEmployees, useMissions } from "@/lib/hooks";

export default function EmployeesPage({ params }: { params: { id: string } }) {
  const companyId = params.id;
  const { data: employees, isLoading } = useEmployees(companyId);
  const { data: missions } = useMissions(companyId);

  return (
    <main className="mx-auto max-w-5xl px-8 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-text">Employees</h1>
        <p className="mt-1 text-sm text-text-muted">Your Department, hired the moment this company was founded.</p>
      </header>

      {isLoading ? (
        <p className="text-sm text-text-muted">Loading employees…</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {employees?.map((employee) => (
            <EmployeeCard
              key={employee.id}
              employee={employee}
              companyId={companyId}
              currentMission={missions?.find((m) => m.id === employee.current_task_id)}
            />
          ))}
        </div>
      )}
    </main>
  );
}
