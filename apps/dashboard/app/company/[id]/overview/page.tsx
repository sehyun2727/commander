import { redirect } from "next/navigation";

// Sprint 13's proof page has been superseded by the real CEO Workspace,
// which now lives at the company landing route itself (DECISIONS.md #223).
// The route is kept (not deleted, per §4.1) so any existing deep link
// still resolves, just to the real implementation instead of a duplicate.
export default function WorkspaceOverviewRedirect({ params }: { params: { id: string } }) {
  redirect(`/company/${params.id}`);
}
