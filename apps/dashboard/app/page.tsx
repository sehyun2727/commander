"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useCompanies, useCreateCompany } from "@/lib/hooks";
import { EmptyState } from "@/components/EmptyState";

export default function CompanyListPage() {
  const { data: companies, isLoading } = useCompanies();
  const createCompany = useCreateCompany();
  const router = useRouter();
  const [name, setName] = useState("");

  async function handleFound(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    const company = await createCompany.mutateAsync(trimmed);
    setName("");
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
        className="mb-8 flex items-center gap-3 rounded-xl border border-base-border bg-base-card p-4 shadow-panel"
      >
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Company name, e.g. Acme AI"
          className="flex-1 rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
        />
        <button
          type="submit"
          disabled={createCompany.isPending || !name.trim()}
          className="shrink-0 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
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
            <Link
              key={company.id}
              href={`/company/${company.id}`}
              className="rounded-xl border border-base-border bg-base-card p-5 shadow-panel transition-colors hover:border-accent/50 hover:bg-base-hover"
            >
              <p className="text-base font-semibold text-text">{company.name}</p>
              <p className="mt-1 text-xs uppercase tracking-wide text-text-faint">Provider: {company.provider}</p>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
