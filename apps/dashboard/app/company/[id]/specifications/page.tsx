"use client";

import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { SpecificationCard } from "@/components/SpecificationCard";
import { StartPlanningForm } from "@/components/StartPlanningForm";
import { useSpecifications } from "@/lib/hooks";

export default function SpecificationsPage({ params }: { params: { id: string } }) {
  const companyId = params.id;
  const { data: specifications, isLoading, isError } = useSpecifications(companyId);

  return (
    <main className="mx-auto max-w-6xl px-8 py-10">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-text">Project Specifications</h1>
          <p className="mt-1 text-sm text-text-muted">
            Where the PM and CTO turn a request into a plan you can approve.
          </p>
        </div>
        <StartPlanningForm companyId={companyId} />
      </header>

      {isLoading ? (
        <p className="text-sm text-text-muted">Loading Project Specifications…</p>
      ) : isError ? (
        <ErrorState description="Couldn't load Project Specifications. Try refreshing in a moment." />
      ) : specifications?.length === 0 ? (
        <EmptyState
          title="No Project Specifications yet"
          description="Start planning above to have the PM and CTO turn a request into a plan you can approve."
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {specifications?.map((specification) => (
            <SpecificationCard key={specification.id} specification={specification} companyId={companyId} />
          ))}
        </div>
      )}
    </main>
  );
}
