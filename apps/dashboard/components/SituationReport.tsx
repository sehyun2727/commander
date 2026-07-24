"use client";

import { AgentAvatar } from "@/components/AgentAvatar";
import { useEmployees, useSituation } from "@/lib/hooks";
import { relativeTime } from "@/lib/utils";

export function SituationReport({ companyId }: { companyId: string }) {
  const { data: situation, isLoading } = useSituation(companyId);
  const { data: employees } = useEmployees(companyId);
  const pm = employees?.find((e) => e.role === "pm");

  if (isLoading || !situation) {
    return (
      <section className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
        <p className="text-sm text-text-faint">Reading the room…</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
      <p className="text-sm leading-relaxed text-text">{situation.text}</p>
      <div className="mt-3 flex items-center gap-2 text-xs text-text-faint">
        {pm && <AgentAvatar name={pm.name} color={pm.avatar_color} size={18} />}
        <span>
          {pm?.name ?? "PM"} · {relativeTime(situation.generated_at)}
        </span>
      </div>
    </section>
  );
}
