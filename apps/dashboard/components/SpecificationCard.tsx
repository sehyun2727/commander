import Link from "next/link";
import type { Specification } from "@/lib/types";
import { relativeTime } from "@/lib/utils";
import { SpecificationStatusBadge } from "./SpecificationStatusBadge";

export function SpecificationCard({ specification, companyId }: { specification: Specification; companyId: string }) {
  return (
    <Link
      href={`/company/${companyId}/specifications/${specification.id}`}
      className="block rounded-lg border border-base-border bg-base-card p-3.5 shadow-panel transition-colors hover:border-accent/40"
    >
      <p className="line-clamp-2 text-sm font-medium text-text">{specification.request_text}</p>
      <div className="mt-3 flex items-center justify-between gap-2">
        <SpecificationStatusBadge status={specification.status} />
        <span className="text-[11px] text-text-faint">{relativeTime(specification.updated_at)}</span>
      </div>
      {specification.current_version > 0 && (
        <p className="mt-2 text-[11px] text-text-faint">Version {specification.current_version}</p>
      )}
    </Link>
  );
}
