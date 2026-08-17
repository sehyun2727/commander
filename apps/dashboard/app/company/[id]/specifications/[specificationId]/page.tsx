import { SpecificationDetail } from "@/components/SpecificationDetail";

export default function SpecificationDetailPage({ params }: { params: { id: string; specificationId: string } }) {
  return <SpecificationDetail companyId={params.id} specificationId={params.specificationId} />;
}
