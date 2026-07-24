"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCompany } from "@/lib/hooks";

export function Sidebar({ companyId }: { companyId: string }) {
  const pathname = usePathname();
  const { data: company } = useCompany(companyId);

  const links = [
    { href: `/company/${companyId}`, label: "Headquarters", exact: true },
    { href: `/company/${companyId}/decisions`, label: "Decisions" },
    { href: `/company/${companyId}/missions`, label: "Missions" },
    { href: `/company/${companyId}/employees`, label: "Employees" },
    { href: `/company/${companyId}/settings`, label: "Company Settings" },
  ];

  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-base-border bg-base-raised">
      <div className="border-b border-base-border px-5 py-4">
        <Link href="/" className="text-xs font-medium uppercase tracking-wider text-text-faint hover:text-text-muted">
          ← All Companies
        </Link>
        <p className="mt-2 truncate text-sm font-semibold text-text">{company?.name ?? "Loading…"}</p>
        {company && (
          <span className="mt-1 inline-block rounded bg-accent-soft px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-accent">
            {company.provider}
          </span>
        )}
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4">
        {links.map((link) => {
          const active = link.exact ? pathname === link.href : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`block rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active ? "bg-accent-soft text-accent" : "text-text-muted hover:bg-base-hover hover:text-text"
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-base-border px-5 py-3 text-[11px] text-text-faint">Commander OS</div>
    </aside>
  );
}
