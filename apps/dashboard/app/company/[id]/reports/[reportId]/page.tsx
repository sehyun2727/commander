import { ReportDetail } from "@/components/ReportDetail";

export default function ReportDetailPage({ params }: { params: { id: string; reportId: string } }) {
  return <ReportDetail companyId={params.id} reportId={params.reportId} />;
}
