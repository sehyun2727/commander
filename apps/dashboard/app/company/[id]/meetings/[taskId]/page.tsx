import { MissionDetail } from "@/components/MissionDetail";

// A Meeting is a Mission's conversation thread — same underlying data as
// the Mission detail view, reached via a separate URL because CEOs think
// of "join the meeting for X" and "look at mission X" as different intents.
export default function MeetingPage({ params }: { params: { id: string; taskId: string } }) {
  return <MissionDetail companyId={params.id} taskId={params.taskId} />;
}
