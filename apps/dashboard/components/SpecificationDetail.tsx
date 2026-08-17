"use client";

import Link from "next/link";
import { useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { SpecificationStatusBadge } from "@/components/SpecificationStatusBadge";
import {
  useAnswerClarification,
  useApproveSpecification,
  useBeginExecution,
  useCancelSpecification,
  useRejectSpecification,
  useRoles,
  useSpecification,
  useSpecificationTurns,
  useSpecificationVersions,
  useSubmitSpecificationRevision,
} from "@/lib/hooks";
import { relativeTime, roleLabel } from "@/lib/utils";

const NOT_CANCELLABLE_STATUSES = new Set(["approved", "rejected", "cancelled", "failed"]);

function VersionSection({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-faint">{label}</p>
      <p className="mt-1 whitespace-pre-wrap text-sm text-text-muted">{value}</p>
    </div>
  );
}

function VersionListSection({ label, items }: { label: string; items?: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-faint">{label}</p>
      <ul className="mt-1 list-disc space-y-0.5 pl-4 text-sm text-text-muted">
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function RisksSection({ risks }: { risks?: { risk: string; mitigation: string }[] }) {
  if (!risks || risks.length === 0) return null;
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-text-faint">Risks</p>
      <ul className="mt-1 space-y-1.5">
        {risks.map((entry, index) => (
          <li key={index} className="text-sm text-text-muted">
            <span className="text-text">{entry.risk}</span>
            {entry.mitigation && <span className="text-text-faint"> — mitigation: {entry.mitigation}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SpecificationDetail({ companyId, specificationId }: { companyId: string; specificationId: string }) {
  const { data: specification, isLoading, isError } = useSpecification(specificationId);
  const { data: turns } = useSpecificationTurns(specificationId);
  const { data: versions } = useSpecificationVersions(specificationId);
  const { data: roles } = useRoles(companyId);

  const [answers, setAnswers] = useState<string[]>([]);
  const [feedback, setFeedback] = useState("");
  const [confirmingCancel, setConfirmingCancel] = useState(false);

  const answerClarification = useAnswerClarification(companyId, specificationId);
  const submitRevision = useSubmitSpecificationRevision(companyId, specificationId);
  const approve = useApproveSpecification(companyId, specificationId);
  const reject = useRejectSpecification(companyId, specificationId);
  const cancel = useCancelSpecification(companyId, specificationId);
  const beginExecution = useBeginExecution(companyId, specificationId);

  if (isLoading) {
    return (
      <main className="mx-auto max-w-3xl px-8 py-10">
        <p className="text-sm text-text-muted">Loading Project Specification…</p>
      </main>
    );
  }

  if (isError || !specification) {
    return (
      <main className="mx-auto max-w-3xl px-8 py-10">
        <Link
          href={`/company/${companyId}/specifications`}
          className="text-xs font-medium text-text-faint hover:text-text-muted"
        >
          ← Project Specifications
        </Link>
        <div className="mt-4">
          <ErrorState
            description={
              isError
                ? "Couldn't load this Project Specification. Try refreshing in a moment."
                : "This Project Specification doesn't exist, or has been removed."
            }
          />
        </div>
      </main>
    );
  }

  const latestVersion = versions?.[versions.length - 1];

  async function handleAnswerClarification(e: React.FormEvent) {
    e.preventDefault();
    if (!specification!.clarification_questions?.length) return;
    await answerClarification.mutateAsync(answers);
    setAnswers([]);
  }

  async function handleSubmitRevision(e: React.FormEvent) {
    e.preventDefault();
    if (!feedback.trim()) return;
    await submitRevision.mutateAsync(feedback.trim());
    setFeedback("");
  }

  return (
    <main className="mx-auto max-w-3xl px-8 py-10">
      <Link
        href={`/company/${companyId}/specifications`}
        className="text-xs font-medium text-text-faint hover:text-text-muted"
      >
        ← Project Specifications
      </Link>

      <header className="mt-3 mb-4 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-text">{specification.request_text}</h1>
          <p className="mt-1 text-xs text-text-faint">Requested {relativeTime(specification.created_at)}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {!NOT_CANCELLABLE_STATUSES.has(specification.status) &&
            (confirmingCancel ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-muted">Cancel this Specification?</span>
                <button
                  onClick={() => cancel.mutate(undefined, { onSettled: () => setConfirmingCancel(false) })}
                  disabled={cancel.isPending}
                  className="rounded-lg bg-status-red px-3 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
                >
                  {cancel.isPending ? "Cancelling…" : "Yes, cancel"}
                </button>
                <button
                  onClick={() => setConfirmingCancel(false)}
                  disabled={cancel.isPending}
                  className="rounded-lg border border-base-border px-3 py-2 text-sm font-medium text-text-muted hover:bg-base-hover disabled:opacity-50"
                >
                  Never mind
                </button>
              </div>
            ) : (
              <button
                onClick={() => setConfirmingCancel(true)}
                className="rounded-lg border border-base-border px-4 py-2 text-sm font-medium text-text-muted hover:bg-base-hover"
              >
                Cancel
              </button>
            ))}
        </div>
      </header>

      <div className="mb-6 flex flex-wrap items-center gap-2">
        <SpecificationStatusBadge status={specification.status} />
        {specification.current_version > 0 && (
          <span className="text-xs uppercase tracking-wide text-text-faint">
            Version {specification.current_version}
          </span>
        )}
      </div>

      {specification.status === "clarification_required" && specification.clarification_questions && (
        <section className="mb-6 rounded-xl border border-accent/30 bg-accent-soft/40 p-4">
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-wide text-accent">
            The CTO needs more information
          </p>
          <form onSubmit={handleAnswerClarification} className="space-y-3">
            {specification.clarification_questions.map((question, index) => (
              <div key={index}>
                <p className="text-sm text-text">{question}</p>
                <textarea
                  value={answers[index] ?? ""}
                  onChange={(e) => {
                    const next = [...answers];
                    next[index] = e.target.value;
                    setAnswers(next);
                  }}
                  rows={2}
                  className="mt-1.5 w-full resize-none rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
                  placeholder="Your answer…"
                />
              </div>
            ))}
            <button
              type="submit"
              disabled={
                answerClarification.isPending ||
                answers.length < specification.clarification_questions.length ||
                answers.some((a) => !a?.trim())
              }
              className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              {answerClarification.isPending ? "Sending…" : "Send Answers"}
            </button>
          </form>
        </section>
      )}

      {latestVersion ? (
        <section className="mb-6 space-y-4 rounded-xl border border-base-border bg-base-card p-4 shadow-panel">
          <h2 className="text-sm font-semibold text-text">{latestVersion.title}</h2>
          <VersionSection label="Problem Statement" value={latestVersion.problem_statement} />
          <VersionListSection label="Goals" items={latestVersion.goals} />
          <VersionListSection label="Non-Goals" items={latestVersion.non_goals} />
          <VersionListSection label="Requirements" items={latestVersion.requirements} />
          <VersionListSection label="Acceptance Criteria" items={latestVersion.acceptance_criteria} />
          <VersionSection label="Technical Approach" value={latestVersion.technical_approach} />
          <VersionListSection label="Architecture Components" items={latestVersion.architecture_components} />
          <VersionSection label="Data / Migration Impact" value={latestVersion.data_migration_impact} />
          <VersionSection label="Security Considerations" value={latestVersion.security_considerations} />
          <VersionSection label="Observability Requirements" value={latestVersion.observability_requirements} />
          <VersionSection label="Test Plan" value={latestVersion.test_plan} />
          <RisksSection risks={latestVersion.risks} />
          <VersionListSection label="Dependencies" items={latestVersion.dependencies} />
          <VersionListSection label="Assumptions" items={latestVersion.assumptions} />
          <VersionListSection label="Unresolved Questions" items={latestVersion.unresolved_questions} />
          <VersionListSection label="Implementation Stages" items={latestVersion.implementation_stages} />
        </section>
      ) : (
        specification.status === "planning" && (
          <EmptyState title="Planning in progress" description="The PM and CTO are still drafting the plan." />
        )
      )}

      {specification.status === "ready_for_review" && (
        <section className="mb-6 rounded-xl border border-accent/30 bg-accent-soft/40 p-4">
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-wide text-accent">Your decision</p>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => approve.mutate()}
              disabled={approve.isPending}
              className="rounded-lg bg-status-green px-3 py-1.5 text-xs font-semibold text-black transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              Approve
            </button>
            <button
              onClick={() => reject.mutate(undefined)}
              disabled={reject.isPending}
              className="rounded-lg border border-status-red/50 bg-status-red-soft px-3 py-1.5 text-xs font-semibold text-status-red transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              Reject
            </button>
          </div>
          <form onSubmit={handleSubmitRevision} className="mt-4">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-text-faint">Request a revision</p>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="What should the PM and CTO change?"
              rows={2}
              className="mt-1.5 w-full resize-none rounded-lg border border-base-border bg-base-raised px-3 py-2 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none"
            />
            <button
              type="submit"
              disabled={submitRevision.isPending || !feedback.trim()}
              className="mt-2 rounded-lg border border-status-amber/50 bg-status-amber-soft px-3 py-1.5 text-xs font-semibold text-status-amber transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {submitRevision.isPending ? "Sending…" : "Request Revision"}
            </button>
          </form>
        </section>
      )}

      {specification.status === "approved" && (
        <section className="mb-6 rounded-xl border border-status-green/30 bg-status-green-soft/40 p-4">
          <p className="mb-3 text-sm text-text">This Project Specification is approved and ready to build.</p>
          <button
            onClick={() => beginExecution.mutate()}
            disabled={beginExecution.isPending}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {beginExecution.isPending ? "Starting…" : "Begin Execution"}
          </button>
        </section>
      )}

      {turns && turns.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold text-text">Planning Meeting</h2>
          <div className="space-y-2.5">
            {turns.map((turn) => (
              <div key={turn.id} className="rounded-lg border border-base-border bg-base-card p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium text-text">
                    {turn.role_key ? roleLabel(roles, turn.role_key) : turn.actor_role}
                  </span>
                  <span className="text-[11px] text-text-faint">{relativeTime(turn.created_at)}</span>
                </div>
                <p className="mt-1.5 whitespace-pre-wrap text-sm text-text-muted">{turn.text}</p>
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
