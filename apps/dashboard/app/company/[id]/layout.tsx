"use client";

import { useEffect, useState } from "react";
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

  // Keyboard users can dismiss the mobile drawer with Escape, matching the
  // backdrop click/close-button affordances already available to pointer
  // users. Also lock body scroll while the drawer covers the page so the
  // content behind it doesn't scroll along with it.
  useEffect(() => {
    if (!navOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setNavOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = prevOverflow;
    };
  }, [navOpen]);

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
