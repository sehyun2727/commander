import { EmployeeProfile } from "@/components/EmployeeProfile";

export default function EmployeeProfilePage({ params }: { params: { id: string; agentId: string } }) {
  return <EmployeeProfile companyId={params.id} agentId={params.agentId} />;
}
