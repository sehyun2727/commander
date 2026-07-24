"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useCompanies, useCreateCompany } from "@/lib/hooks";
import { CompanyCard } from "@/components/CompanyCard";
import { EmptyState } from "@/components/EmptyState";

export default function CompanyListPage() {
  const { data: companies, isLoading } = useCompanies();
  const createCompany = useCreateCompany();
  const router = useRouter();
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");

  async function handleFound(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    const company = await createCompany.mutateAsync(trimmed);
    const trimmedPurpose = purpose.trim();
    // Founding invitation is name + one optional "what it should build"
    // field (UX_SPEC §3.1) -- if the CEO fills it in, skip the Missions
    // empty-state suggestion and get straight to a live Mission. Calls
    // the API directly (not useCreateMission) since this is a one-off
    // imperative side effect, not a hook the component re-renders with.
    if (trimmedPurpose) {
      await api.createMission(company.id, {
        title: trimmedPurpose.length > 80 ? `${trimmedPurpose.slice(0, 80)}…` : trimmedPurpose,
        description: trimmedPurpose,
        priority: "normal",
      });
    }
    setName("");
    setPurpose("");
    router.push(`/company/${company.id}`);
  }

  const active = companies?.filter((c) => !c.archived) ?? [];

  return (
    <main className="mx-auto min-h-screen max-w-4xl px-6 py-16">
      <header className="mb-10">
        <h1 className="text-2xl font-semibold text-text">Commander</h1>
        <p className="mt-1 text-sm text-text-muted">Run your AI software companies. Pick one, or found a new one.</p>
      </header>

      <form
        onSubmit={handleFound}
        className="mb-8 space-y-3 rounded-xl border border-base-border bg-base-card p-4 shadow-panel"
      >
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Company name, e.g. Acme AI"
          className="w-full rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
        />
        <input
          value={purpose}
          onChange={(e) => setPurpose(e.target.value)}
          placeholder="What should it build? (optional)"
          className="w-full rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
        />
        <button
          type="submit"
          disabled={createCompany.isPending || !name.trim()}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          {createCompany.isPending ? "Founding…" : "Found Company"}
        </button>
      </form>

      {isLoading ? (
        <p className="text-sm text-text-muted">Loading companies…</p>
      ) : active.length === 0 ? (
        <EmptyState
          title="No companies yet"
          description="Found your first AI company above to hire a Department and start assigning Missions."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {active.map((company) => (
            <CompanyCard key={company.id} company={company} />
          ))}
        </div>
      )}
    </main>
  );
}
