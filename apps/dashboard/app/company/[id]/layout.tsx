import { RealtimeProvider } from "@/components/RealtimeProvider";
import { Sidebar } from "@/components/Sidebar";

export default function CompanyLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: { id: string };
}) {
  return (
    <RealtimeProvider companyId={params.id}>
      <div className="flex min-h-screen">
        <Sidebar companyId={params.id} />
        <div className="flex-1 overflow-y-auto">{children}</div>
      </div>
    </RealtimeProvider>
  );
}
