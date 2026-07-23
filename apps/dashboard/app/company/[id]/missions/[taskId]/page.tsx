import { MissionDetail } from "@/components/MissionDetail";

export default function MissionDetailPage({ params }: { params: { id: string; taskId: string } }) {
  return <MissionDetail companyId={params.id} taskId={params.taskId} />;
}
