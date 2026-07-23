"use client";

import { useState } from "react";
import { useCreateMission } from "@/lib/hooks";

export function NewMissionForm({ companyId }: { companyId: string }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("normal");
  const create = useCreateMission(companyId);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    await create.mutateAsync({ title: title.trim(), description, priority });
    setTitle("");
    setDescription("");
    setPriority("normal");
    setOpen(false);
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
      >
        + New Mission
      </button>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[2fr_1fr]">
        <input
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Mission title"
          className="rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
        />
        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
          className="rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text focus:border-accent focus:outline-none"
        >
          <option value="low">Low priority</option>
          <option value="normal">Normal priority</option>
          <option value="high">High priority</option>
          <option value="urgent">Urgent</option>
        </select>
      </div>
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Brief for the Department (what does done look like?)"
        rows={2}
        className="mt-3 w-full resize-none rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
      />
      <div className="mt-3 flex gap-2">
        <button
          type="submit"
          disabled={create.isPending || !title.trim()}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {create.isPending ? "Creating…" : "Create Mission"}
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
