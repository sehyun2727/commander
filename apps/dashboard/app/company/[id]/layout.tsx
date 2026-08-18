"use client";

import { useState } from "react";
import { RealtimeProvider } from "@/components/RealtimeProvider";
import { Sidebar } from "@/components/Sidebar";
import { RequireAuth } from "@/components/RequireAuth";
import { AccountBadge } from "@/components/AccountBadge";
import { MobileHeader } from "@/components/MobileHeader";

export default function CompanyLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { id: string };
}) {
  const [navOpen, setNavOpen] = useState(false);

  return (
    <RequireAuth>
      {/* Remounted on company switch (key={params.id}) so buffered
          Timeline events / streaming replies / SSE connection status never
          leak from the previous company (DECISIONS.md #224). */}
      <RealtimeProvider key={params.id} companyId={params.id}>
        <div className="flex min-h-screen flex-col lg:flex-row">
          <MobileHeader companyId={params.id} onOpenNav={() => setNavOpen(true)} />
          <Sidebar companyId={params.id} mobileOpen={navOpen} onClose={() => setNavOpen(false)} />
          <div className="relative flex-1 overflow-y-auto">
            <div className="absolute right-6 top-4 z-10 hidden lg:block">
              <AccountBadge />
            </div>
            {children}
          </div>
        </div>
      </RealtimeProvider>
    </RequireAuth>
  );
}
