import { RealtimeProvider } from "@/components/RealtimeProvider";
import { Sidebar } from "@/components/Sidebar";
import { RequireAuth } from "@/components/RequireAuth";
import { AccountBadge } from "@/components/AccountBadge";

export default function CompanyLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { id: string };
}) {
  return (
    <RequireAuth>
      <RealtimeProvider companyId={params.id}>
        <div className="flex min-h-screen">
          <Sidebar companyId={params.id} />
          <div className="relative flex-1 overflow-y-auto">
            <div className="absolute right-6 top-4 z-10">
              <AccountBadge />
            </div>
            {children}
          </div>
        </div>
      </RealtimeProvider>
    </RequireAuth>
  );
}
