"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useArchiveCompany, useCompany, useModels, useSetModel, useUpdateCompanySettings } from "@/lib/hooks";

const ROLE_LABEL: Record<string, string> = { planner: "PM", builder: "Engineer", reviewer: "Reviewer" };

export default function SettingsPage({ params }: { params: { id: string } }) {
  const companyId = params.id;
  const router = useRouter();
  const { data: company } = useCompany(companyId);
  const updateSettings = useUpdateCompanySettings(companyId);
  const archive = useArchiveCompany(companyId);
  const { data: models } = useModels(companyId);
  const setModel = useSetModel(companyId);

  const [name, setName] = useState("");
  const [provider, setProvider] = useState<"mock" | "anthropic">("mock");
  const [apiKey, setApiKey] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (company) {
      setName(company.name);
      setProvider(company.provider);
    }
  }, [company]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaved(false);
    await updateSettings.mutateAsync({
      name,
      provider,
      ...(apiKey.trim() ? { anthropic_api_key: apiKey.trim() } : {}),
    });
    setApiKey("");
    setSaved(true);
  }

  async function handleArchive() {
    if (!window.confirm(`Archive "${company?.name}"? This company will be hidden from the company list.`)) return;
    await archive.mutateAsync();
    router.push("/");
  }

  return (
    <main className="mx-auto max-w-2xl px-8 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-semibold text-text">Company Settings</h1>
        <p className="mt-1 text-sm text-text-muted">Rename the company, switch AI providers, and manage credentials.</p>
      </header>

      <form onSubmit={handleSave} className="space-y-5 rounded-xl border border-base-border bg-base-card p-6 shadow-panel">
        <div>
          <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-text-faint">Company name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
          />
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-text-faint">AI Provider</label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as "mock" | "anthropic")}
            className="w-full rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
          >
            <option value="mock">Mock (no API key required)</option>
            <option value="anthropic">Anthropic</option>
          </select>
          <p className="mt-1.5 text-xs text-text-faint">
            Mock produces deterministic, templated Employee output — useful for demos and testing without spending
            API credits.
          </p>
        </div>

        {provider === "anthropic" && (
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-text-faint">
              Anthropic API Key
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Leave blank to keep the current key"
              autoComplete="off"
              className="w-full rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
            />
            <p className="mt-1.5 text-xs text-text-faint">
              Write-only: once saved, the key is never sent back to the browser.
            </p>
          </div>
        )}

        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={updateSettings.isPending}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {updateSettings.isPending ? "Saving…" : "Save Changes"}
          </button>
          {saved && <span className="text-xs text-status-green">Saved.</span>}
        </div>
      </form>

      <div className="mt-8 rounded-xl border border-base-border bg-base-card p-6 shadow-panel">
        <p className="text-sm font-semibold text-text">Employee Models</p>
        <p className="mt-1 text-xs text-text-muted">
          Choose which model backs each Employee's work. Changes apply immediately — no restart required.
        </p>
        <div className="mt-4 space-y-4">
          {models?.map((entry) => {
            const orderedOptions = [
              entry.recommended_model,
              ...entry.options.filter((option) => option !== entry.recommended_model),
            ];
            return (
              <div key={entry.role} className="flex items-center justify-between gap-4">
                <label className="text-sm font-medium text-text">{ROLE_LABEL[entry.role] ?? entry.role}</label>
                <select
                  value={entry.current_model}
                  disabled={setModel.isPending}
                  onChange={(e) => setModel.mutate({ role: entry.role, model: e.target.value })}
                  className="w-64 rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text focus:border-accent focus:outline-none disabled:opacity-50"
                >
                  {orderedOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                      {option === entry.recommended_model ? " (Recommended)" : ""}
                    </option>
                  ))}
                </select>
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-8 rounded-xl border border-status-red/30 bg-status-red-soft/30 p-6">
        <p className="text-sm font-semibold text-text">Danger Zone</p>
        <p className="mt-1 text-xs text-text-muted">Archiving hides this company from the company list. This cannot be undone from the UI.</p>
        <button
          onClick={handleArchive}
          disabled={archive.isPending}
          className="mt-3 rounded-lg border border-status-red/50 px-4 py-2 text-sm font-medium text-status-red hover:bg-status-red-soft disabled:opacity-50"
        >
          {archive.isPending ? "Archiving…" : "Archive Company"}
        </button>
      </div>
    </main>
  );
}
