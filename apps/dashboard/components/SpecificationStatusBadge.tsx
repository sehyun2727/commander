import type { Specification } from "@/lib/types";
import type { Tone } from "@/lib/utils";
import { StatusPill } from "./StatusPill";

// Sprint 12 §4.6: the 9-state SpecificationStatus machine, mirroring
// StatusWord.tsx's map-not-branch pattern for the CEO-facing label/tone.
const STATUS_LABEL: Record<Specification["status"], string> = {
  draft: "Draft",
  planning: "Planning",
  clarification_required: "Needs your input",
  ready_for_review: "Ready for your review",
  approved: "Approved",
  revision_requested: "Revision requested",
  rejected: "Rejected",
  cancelled: "Cancelled",
  failed: "Failed — see report",
};

const STATUS_TONE: Record<Specification["status"], Tone> = {
  draft: "gray",
  planning: "gray",
  clarification_required: "amber",
  ready_for_review: "amber",
  approved: "green",
  revision_requested: "amber",
  rejected: "red",
  cancelled: "red",
  failed: "red",
};

export function specificationStatusLabel(status: Specification["status"]): string {
  return STATUS_LABEL[status];
}

export function specificationStatusTone(status: Specification["status"]): Tone {
  return STATUS_TONE[status];
}

export function SpecificationStatusBadge({ status }: { status: Specification["status"] }) {
  return <StatusPill tone={specificationStatusTone(status)} label={specificationStatusLabel(status)} />;
}
