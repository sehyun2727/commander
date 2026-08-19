"""Sprint 18 §4/§5 -- one extractor per projected `EventType`.

DECISIONS.md #244: each extractor is `async def extract_xxx(event, session)
-> ExtractedRecord | None`, not a literally payload-only pure function --
every `Payload` subclass has `extra="forbid"` and most projected events
carry only ids, so richer fields (subject, title, problem_statement,
branch_name, code_stats, turn text, ...) are hydrated from the shared ORM
floor via a direct `session` query (never a cross-module service import --
Rule #1). No `ProviderGateway` call anywhere in this file (Rule #4, brief
§4.2): every field written here is copied or trivially derived from an
already-persisted row, never generated or summarized by a model.

A malformed payload, a missing id, or a row that no longer exists all
return `None` -- logged at INFO, never raised (sprint-18.md §4.6/§9).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.db_models import (
    ApprovalORM,
    SpecificationTurnORM,
    SpecificationVersionORM,
    TaskORM,
)
from ...core.events.base import Event
from ...core.events.types import EventType
from .bounding import bound_text, build_keywords_text, cap_content_json, cap_tags, redact_environment_like_content
from .registry import (
    CEO_APPROVALS,
    FAILED_ATTEMPTS,
    MAX_TITLE_LENGTH,
    PM_SPECIFICATIONS,
    PRIOR_DISCUSSIONS,
    REVIEWER_FEEDBACK,
    SUCCESSFUL_SOLUTIONS,
    tokenize,
)

logger = logging.getLogger("commander.memory")

_DEFAULT_FAILURE_REASON = "Mission failed (no reason recorded)."


@dataclass
class ExtractedRecord:
    """Insert-ready projection output. Not the full `MemoryRecord` --
    `id`/`project_id`/`created_at` are assigned by `service.record_memory`
    at insert time (DECISIONS.md #244)."""

    category: str
    title: str
    content_json: dict
    tags: list[str]
    keywords_text: str
    source_task_id: str | None = None
    source_specification_id: str | None = None


def _bounded_title(title: str) -> str:
    return title[:MAX_TITLE_LENGTH]


_APPROVAL_DECISIONS = {
    EventType.APPROVAL_GRANTED: "approved",
    EventType.APPROVAL_REJECTED: "rejected",
    EventType.APPROVAL_CHANGES_REQUESTED: "changes_requested",
}


async def extract_from_approval_decision(event: Event, session: AsyncSession) -> ExtractedRecord | None:
    approval_id = event.payload.get("approval_id")
    if not isinstance(approval_id, str) or not approval_id:
        logger.info("memory: %s payload missing approval_id, skipping", event.type)
        return None
    decision = _APPROVAL_DECISIONS.get(event.type)
    if decision is None:
        logger.info("memory: unexpected event type %s for approval extractor", event.type)
        return None
    approval = await session.get(ApprovalORM, approval_id)
    if approval is None:
        logger.info("memory: approval %s not found, skipping", approval_id)
        return None
    comment = bound_text(approval.comment or "")
    preview = bound_text(comment or approval.subject, max_bytes=300)
    title = _bounded_title(f"CEO {decision}: {approval.subject}")
    content = cap_content_json(
        {
            "approval_id": approval_id,
            "task_id": approval.task_id,
            "subject": bound_text(approval.subject),
            "decision": decision,
            "comment": comment,
            "preview": preview,
        }
    )
    tags = cap_tags([f"decision:{decision}", f"task:{approval.task_id}"])
    keywords_text = build_keywords_text(approval.subject, comment)
    return ExtractedRecord(
        category=CEO_APPROVALS,
        title=title,
        content_json=content,
        tags=tags,
        keywords_text=keywords_text,
        source_task_id=approval.task_id,
    )


async def extract_from_specification_approved(event: Event, session: AsyncSession) -> ExtractedRecord | None:
    specification_id = event.payload.get("specification_id")
    version = event.payload.get("version")
    if not isinstance(specification_id, str) or not specification_id or not isinstance(version, int):
        logger.info("memory: SPECIFICATION_APPROVED payload malformed, skipping")
        return None
    result = await session.execute(
        select(SpecificationVersionORM).where(
            SpecificationVersionORM.specification_id == specification_id,
            SpecificationVersionORM.version == version,
        )
    )
    spec_version = result.scalar_one_or_none()
    if spec_version is None:
        logger.info("memory: specification version %s/%s not found, skipping", specification_id, version)
        return None
    title = _bounded_title(spec_version.title or f"Specification {specification_id[:8]}")
    goals = [bound_text(g, max_bytes=300) for g in (spec_version.goals or [])[:20]]
    requirements = [bound_text(r, max_bytes=300) for r in (spec_version.requirements or [])[:20]]
    acceptance_criteria = [bound_text(a, max_bytes=300) for a in (spec_version.acceptance_criteria or [])[:20]]
    problem_statement = bound_text(spec_version.problem_statement or "")
    content = cap_content_json(
        {
            "specification_id": specification_id,
            "version": version,
            "title": title,
            "problem_statement": problem_statement,
            "goals": goals,
            "requirements": requirements,
            "acceptance_criteria": acceptance_criteria,
            "preview": bound_text(problem_statement, max_bytes=300),
        }
    )
    tags = cap_tags([f"spec:{specification_id}", f"version:{version}", *tokenize(title)[:8]])
    keywords_text = build_keywords_text(
        title, problem_statement, " ".join(goals), " ".join(requirements), " ".join(acceptance_criteria)
    )
    return ExtractedRecord(
        category=PM_SPECIFICATIONS,
        title=title,
        content_json=content,
        tags=tags,
        keywords_text=keywords_text,
        source_specification_id=specification_id,
    )


async def extract_from_review_completed(event: Event, session: AsyncSession) -> ExtractedRecord | None:
    task_id = event.payload.get("task_id")
    outcome = event.payload.get("outcome")
    if not isinstance(task_id, str) or not task_id or not isinstance(outcome, str) or not outcome:
        logger.info("memory: REVIEW_COMPLETED payload malformed, skipping")
        return None
    raw_sections = event.payload.get("sections")
    sections = raw_sections if isinstance(raw_sections, dict) else {}
    bounded_sections = {str(k): bound_text(str(v)) for k, v in sections.items() if isinstance(k, str)}
    title = _bounded_title(f"Review {outcome} -- task {task_id[:8]}")
    preview_source = next(iter(bounded_sections.values()), "")
    content = cap_content_json(
        {
            "task_id": task_id,
            "outcome": outcome,
            "sections": bounded_sections,
            "preview": bound_text(preview_source, max_bytes=300),
        }
    )
    tags = cap_tags([f"outcome:{outcome}", f"task:{task_id}"])
    keywords_text = build_keywords_text(title, *bounded_sections.values())
    return ExtractedRecord(
        category=REVIEWER_FEEDBACK,
        title=title,
        content_json=content,
        tags=tags,
        keywords_text=keywords_text,
        source_task_id=task_id,
    )


async def extract_from_task_failed(event: Event, session: AsyncSession) -> ExtractedRecord | None:
    task_id = event.payload.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        logger.info("memory: TASK_FAILED payload missing task_id, skipping")
        return None
    reason_code = event.payload.get("reason_code")
    if reason_code is not None and not isinstance(reason_code, str):
        reason_code = None
    task = await session.get(TaskORM, task_id)
    if task is None:
        logger.info("memory: task %s not found, skipping", task_id)
        return None
    raw_reason = event.reason or _DEFAULT_FAILURE_REASON
    reason_text = bound_text(redact_environment_like_content(raw_reason))
    preview = bound_text(reason_text, max_bytes=300)
    title = _bounded_title(f"Mission failed: {task.title}")
    content = cap_content_json(
        {
            "task_id": task_id,
            "title": bound_text(task.title),
            "reason_code": reason_code,
            "reason": reason_text,
            "preview": preview,
        }
    )
    tag_list = [f"task:{task_id}"]
    if reason_code:
        tag_list.append(f"reason_code:{reason_code}")
    tag_list.extend(tokenize(task.title))
    tags = cap_tags(tag_list)
    keywords_text = build_keywords_text(task.title, reason_text)
    return ExtractedRecord(
        category=FAILED_ATTEMPTS,
        title=title,
        content_json=content,
        tags=tags,
        keywords_text=keywords_text,
        source_task_id=task_id,
    )


async def extract_from_task_completed(event: Event, session: AsyncSession) -> ExtractedRecord | None:
    task_id = event.payload.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        logger.info("memory: TASK_COMPLETED payload missing task_id, skipping")
        return None
    task = await session.get(TaskORM, task_id)
    if task is None:
        logger.info("memory: task %s not found, skipping", task_id)
        return None
    check_results = task.check_results if isinstance(task.check_results, list) else []
    passed = sum(1 for c in check_results if isinstance(c, dict) and c.get("status") == "passed")
    total = len(check_results)
    code_stats = task.code_stats if isinstance(task.code_stats, dict) else {}
    title = _bounded_title(f"Mission completed: {task.title}")
    preview = f"{passed}/{total} checks passed" if total else "No automated checks recorded"
    content = cap_content_json(
        {
            "task_id": task_id,
            "title": bound_text(task.title),
            "branch_name": task.branch_name,
            "code_stats": code_stats,
            "checks_passed": passed,
            "checks_total": total,
            "preview": preview,
        }
    )
    tags = cap_tags([f"task:{task_id}", *tokenize(task.title)])
    keywords_text = build_keywords_text(task.title, preview)
    return ExtractedRecord(
        category=SUCCESSFUL_SOLUTIONS,
        title=title,
        content_json=content,
        tags=tags,
        keywords_text=keywords_text,
        source_task_id=task_id,
    )


async def extract_from_specification_turn_posted(event: Event, session: AsyncSession) -> ExtractedRecord | None:
    specification_id = event.payload.get("specification_id")
    turn_index = event.payload.get("turn_index")
    if not isinstance(specification_id, str) or not specification_id or not isinstance(turn_index, int):
        logger.info("memory: SPECIFICATION_TURN_POSTED payload malformed, skipping")
        return None
    result = await session.execute(
        select(SpecificationTurnORM).where(
            SpecificationTurnORM.specification_id == specification_id,
            SpecificationTurnORM.turn_index == turn_index,
        )
    )
    turn = result.scalar_one_or_none()
    if turn is None:
        logger.info("memory: specification turn %s/%s not found, skipping", specification_id, turn_index)
        return None
    excerpt = bound_text(turn.text)
    title = _bounded_title(f"{turn.kind} turn #{turn_index} ({turn.actor_role})")
    tag_list = [f"spec:{specification_id}", f"kind:{turn.kind}"]
    if turn.role_key:
        tag_list.append(f"role:{turn.role_key}")
    content = cap_content_json(
        {
            "specification_id": specification_id,
            "turn_index": turn_index,
            "actor_role": turn.actor_role,
            "role_key": turn.role_key,
            "kind": turn.kind,
            "excerpt": excerpt,
            "preview": bound_text(turn.text, max_bytes=300),
        }
    )
    tags = cap_tags(tag_list)
    keywords_text = build_keywords_text(title, excerpt)
    return ExtractedRecord(
        category=PRIOR_DISCUSSIONS,
        title=title,
        content_json=content,
        tags=tags,
        keywords_text=keywords_text,
        source_specification_id=specification_id,
    )


EXTRACTORS = {
    EventType.APPROVAL_GRANTED: extract_from_approval_decision,
    EventType.APPROVAL_REJECTED: extract_from_approval_decision,
    EventType.APPROVAL_CHANGES_REQUESTED: extract_from_approval_decision,
    EventType.SPECIFICATION_APPROVED: extract_from_specification_approved,
    EventType.REVIEW_COMPLETED: extract_from_review_completed,
    EventType.TASK_FAILED: extract_from_task_failed,
    EventType.TASK_COMPLETED: extract_from_task_completed,
    EventType.SPECIFICATION_TURN_POSTED: extract_from_specification_turn_posted,
}
