# Sprint 18 — Project Memory (deterministic, PM-triggered recall)

Execute this sprint autonomously from Phase 0 through Phase 4.

Expected baseline:
- local HEAD: 5017b13
- origin/master: 5017b13
- backend baseline: 472 passed / 6 skipped
  (2 of the 6 skips are Windows symlink-privilege skips in
  `test_agent_harness_guards.py` — expected on Windows dev, absent on Linux)
- dashboard typecheck/build: PASS (19 routes compile)
- migration head: `b1f4c8d5e9a2_harness_tool_calls`
- mock E2E with zero provider keys: PASS
- browser-rendered interaction verification: UNVERIFIED (Sprint 17 introduced no CEO-facing UI, matching Sprint 16 precedent)

Repository and git state are authoritative. Verify every baseline claim first.

Follow the current CLAUDE.md, architecture, decisions, UX specification, security constraints, progress discipline, verification standards, and reporting format.

Do not stop for routine confirmation. Stop only for a hard blocker, destructive ambiguity, security/cost exposure, or irreconcilable architectural conflict.

---

## 1. Goal

Give Commander a **first, honest, deterministic organizational memory**: a Company-scoped, event-derived projection that the PM can *explicitly* consult during PM↔CTO planning to bring prior decisions, prior specifications, prior Reviewer verdicts, and — thanks to Sprint 17 — prior mission failures and Employee surrenders into a new planning turn.

At the end of Sprint 18:

1. Selected Timeline events are projected, on publish, into structured Memory records via deterministic (no-LLM) extraction rules.
2. Six of the eight `docs/ARCHITECTURE.md §5` Memory categories are populated automatically: `ceo_approvals`, `pm_specifications`, `reviewer_feedback`, `failed_attempts`, `successful_solutions`, `prior_discussions`. The remaining two (`architecture_decisions`, `coding_conventions`) are explicitly deferred and documented as such.
3. Memory is **Company-scoped only** — every record carries `project_id`, no cross-Company reads exist.
4. Memory is **not a second source of truth** (Rule #14) — every record's provenance is a specific event, deduplicated via `UNIQUE(source_event_id)`.
5. Storage is a new table `memory_records`, populated by an EventBus subscriber, and initially backfilled once from the existing event stream via an idempotent routine.
6. The PM may recall Memory only by including a structured `recall_request` field in its planning-turn JSON output — the orchestrator honors it deterministically between turns and injects a bounded result summary into the next user message.
7. Nothing else fires recall automatically. Not the Engineer, not the CTO, not `_run_engineer_tool_loop`, not `_run_pipeline`, not any HTTP client.
8. Ranking is deterministic: `(tag matches + keyword substring matches) × recency decay`, tie-broken on `created_at` desc then `id` asc. **No provider judgment, no vector, no embedding, no LLM summarization anywhere in the projection or recall path.**
9. Every recall is bounded: server-enforced `MAX_RECALL_LIMIT`, capped `tags`/`keywords` counts and lengths, capped `since_days` lookback.
10. Two new observability events (`memory.recorded`, `memory.recalled`) publish with tiny payloads — never memory bodies, never raw content.
11. No public recall API. No CEO-facing UI change in this sprint. Memory is internal PM planning context.
12. Sprint 17's `TASK_FAILED.reason_code` and self-correction/surrender audit signal is the primary input for the `failed_attempts` category — Sprint 18 must project it faithfully so a future planning session can honestly answer "did this kind of Mission fail before, and how?"
13. Existing planning, specification, mission, workspace, widget, harness, and self-correction behavior remains functional. Planning runs that don't ask for recall behave exactly as they did in Sprint 12/17.
14. Full mock E2E with zero provider keys still passes; a new mock scenario exercises the recall integration end-to-end.

This sprint builds the deterministic Memory foundation the ARCHITECTURE.md §5 roadmap has described since V1. It does not build RAG/vector retrieval, cross-Company memory, Employee-side recall, autonomous cross-Mission learning, an LLM-generated memory summary layer, or any CEO-visible memory surface.

---

## 2. Security Model

Memory records are derived from already-published Events. Events themselves are trusted structured facts written by server-owned code (Rule #3, Rule #8). Memory therefore inherits their trust level, with these additional constraints:

- **All Memory reads are Company-scoped.** Recall queries always filter by `project_id`. There is no code path that reads a Memory record for a different Company than the query's own.
- **Memory records never store raw provider text bodies.** For each source event, project only structured fields (title, reason_code, verdict, task id, bounded excerpt) — never the entire `payload` blob, never a full Employee reply, never raw file content, never sandbox output. Every bounded excerpt uses `agent_harness.output.bound_output` with an explicit low cap.
- **Recall parameters are untrusted only when they originate from a PM's JSON response.** The provider produced them, so validate strictly: cap `tags` count and length, cap `keywords` count and length, cap `since_days`, cap `limit` (server-enforced ceiling regardless of what PM asks for).
- **No new public HTTP endpoint** exposes recall or memory contents. The recall function is called only by `PlanningOrchestrator` in-process; there is no `POST /api/memory/recall`, no `GET /api/memory`, and no admin route.
- **`memory.recorded` / `memory.recalled` payloads carry ids and small counts, never bodies.** A subscriber to the SSE stream can see "a memory was recorded" and "a recall returned N results" — never the content of either.
- **The projection subscriber must not raise into `EventBus.publish`.** Existing subscribers already log-and-swallow (`event_bus/bus.py:60-63`); the memory subscriber follows the same rule. A projection bug can never break a publish.
- **Deduplication is DB-enforced** via `UNIQUE(source_event_id)` on `memory_records`. Race between real-time subscriber and backfill cannot double-project a single event.

Everything Sprint 16/17 established about the Agent Harness (tool authorization, path safety, patch atomicity, process isolation, output redaction, cancellation, budgets, audit) is untouched by this sprint. Memory does not add tools, does not touch the workspace, does not spawn processes, does not run inside the sandbox.

---

## 3. Required Repository Inspection

Before changing code, inspect at minimum:

- CLAUDE.md — Rules #1, #3, #8, #10, #11, #14, #15, #18 apply directly
- PROGRESS.txt (currently "SPRINT 17 DONE. Now working on: nothing -- awaiting Sprint 18 brief")
- README.md
- FOR_CTO.md — the current CTO handover, especially §5 (Domain Model), §6 (Planning), §8 (Events)
- docs/ARCHITECTURE.md, especially §5 (Project Memory target), §6 (module map), §7 (Security)
- docs/DECISIONS.md #233–#242 (Sprint 16 + 17 as-shipped)
- docs/design/UX_SPEC.md
- git history through 5017b13
- `apps/api/app/core/events/types.py` — every `EventType` this sprint's projection may subscribe to
- `apps/api/app/core/events/contracts.py` — every payload model; identify what structured fields are already carried
- `apps/api/app/core/events/base.py` — the `Event` envelope shape
- `apps/api/app/modules/event_bus/bus.py` — how subscribers are registered (`subscribe(EventType, handler)`); how `publish` fans out; how failures are swallowed
- `apps/api/app/modules/planning/orchestrator.py` — the JSON turn-kind dispatch, `_VALIDATORS`, and how a turn's parsed data becomes the next user message
- `apps/api/app/modules/planning/service.py` — where planning is orchestrated (`start_planning`, `resume_after_clarification`, `submit_revision`)
- `apps/api/app/templates/software_company.py::_PM_PLANNING_CONTRACT` and `_CTO_PLANNING_CONTRACT` — the JSON contract text the PM/CTO get
- `apps/api/app/main.py::lifespan` — where singletons and subscribers must be wired; where startup backfill would run
- `apps/api/app/core/db_models.py` — pattern for a new ORM table (see `HarnessToolCallORM` as the closest precedent)
- `apps/api/alembic/versions/b1f4c8d5e9a2_harness_tool_calls.py` — reference migration shape for a new table
- `apps/api/app/core/ownership.py` — how to gate cross-account reads (though Memory never surfaces publicly, follow the same discipline)
- `apps/api/app/modules/tasks/service.py` — how existing services persist and read scoped-by-project data
- `apps/api/app/modules/agent_harness/output.py::bound_output` — the truncation utility to reuse for any excerpt persisted or emitted
- `apps/api/tests/test_planning_orchestrator.py` — the FakeGateway planning-turn pattern to mirror
- `apps/api/tests/test_event_bus.py` — how subscribers are tested
- Sprint 17's `HarnessToolCallORM` audit rows (including `_loop:*` synthetic rows) — are these directly relevant to Memory? Answer: **no, not directly**. Memory reads events, not audit rows. Sprint 17's `TASK_FAILED.reason_code` (published on the pipeline's structured failure paths) is what carries the self-correction/surrender signal into Memory.

Search specifically for:

- every `EventType` currently emitted (audit which are worth projecting)
- every location that publishes events with `kind = "conversation"` (these are Meeting messages; deliberately NOT projected — cross-referencing them would leak conversation into Memory and blur `kind` semantics per Rule #8)
- any existing "subscriber" pattern in `event_bus.subscribe(...)` calls
- any existing project-scoped read patterns for guidance on Memory recall's own read shape

Document existing execution paths before wrapping or extending them.

---

## 4. Approved Decisions

### 4.1 Scope — six categories, deterministic, event-derived

Sprint 18 projects six of `docs/ARCHITECTURE.md §5`'s eight Memory categories, each derived deterministically from an existing event type:

| Category | Source `EventType` | Extractor produces |
|---|---|---|
| `ceo_approvals` | `APPROVAL_GRANTED` / `APPROVAL_REJECTED` / `APPROVAL_CHANGES_REQUESTED` | approval id, task id, subject, decision, bounded comment |
| `pm_specifications` | `SPECIFICATION_APPROVED` | spec id, current version, title, problem_statement, goals, requirements, acceptance_criteria (structured lists, not raw text blob) |
| `reviewer_feedback` | `REVIEW_COMPLETED` | task id, outcome, bounded sections (Problem/Recommendation/Risk/Impact) |
| `failed_attempts` | `TASK_FAILED` (Sprint 17 `reason_code` included when present) | task id, title, reason_code, bounded reason string |
| `successful_solutions` | `TASK_COMPLETED` | task id, title, branch_name, code_stats summary, check_results pass/total counts |
| `prior_discussions` | `SPECIFICATION_TURN_POSTED` | spec id, turn_index, actor_role, role_key, kind, bounded text excerpt |

Excluded from Sprint 18 (explicit non-goal, not oversight):

- `architecture_decisions` — no event in the current stream carries these as first-class structured facts. Adding a category that projects DECISIONS.md entries would require a new writing mechanism, which is a design in its own right — defer.
- `coding_conventions` — likewise not derivable from any existing event. Would require a Reviewer/PM to explicitly emit a `convention_recorded` event, which is a Sprint 19+ decision.

Conversation events (`CONVERSATION_MESSAGE`, `CONVERSATION_MESSAGE_DELTA`) are **never** projected. They are `kind = "conversation"` — Meeting content, not organizational fact. Projecting them would blur Rule #8 (`kind` affects rendering, not what counts as company memory) and would balloon storage with raw Employee reply text.

### 4.2 Deterministic projection only — no LLM anywhere

Projection is a pure function of an already-persisted event's structured payload. Under no circumstance does the projection module call `ProviderGateway`, request a summary, or ask a model to classify an event. Every extractor is code that reads specific payload fields and writes structured output. This is the load-bearing invariant that makes Memory reproducible, cheap, and fast.

Recall is likewise deterministic: keyword/tag/recency arithmetic only. No `gateway.complete(...)` in the recall path.

### 4.3 Storage — new `memory_records` table, one migration

Add `MemoryRecordORM` to `core/db_models.py` and one Alembic migration on top of `b1f4c8d5e9a2`. Shape:

```
id                      String, PK, uuid
project_id              FK projects.id, indexed
category                String, indexed (one of the 6 category strings above)
source_event_id         FK events.id, UNIQUE (dedup)
source_task_id          FK tasks.id, nullable, indexed
source_specification_id FK specifications.id, nullable, indexed
title                   String (bounded, human-readable label)
content_json            JSON (structured, bounded per §4.4)
tags                    JSON list[str] (bounded — max 16 tags, each ≤ 64 chars, lowercased)
keywords_text           Text (denormalized, lowercased, bounded ≤ 4096 chars — for substring match)
created_at              DateTime(timezone=True), indexed
```

Migration must round-trip on real Postgres. The `UNIQUE(source_event_id)` constraint is the deduplication guarantee — a re-run of the backfill routine or a race between the subscriber and a manual backfill can never create a duplicate record for the same event.

`memory_records` never grows a column that carries the source event's `payload` verbatim. Every field above is either an id, a bounded excerpt, or structured extracted data.

### 4.4 Bounded content per record

Every extractor must:

- Truncate `title` to ≤ 200 chars.
- Truncate any excerpted text field in `content_json` via `agent_harness.output.bound_output` with a local cap ≤ 2048 bytes per field.
- Cap total `content_json` size at ≤ 8 KiB serialized; if an extractor exceeds this, drop the largest text field with a `"_truncated": true` marker rather than persist an unbounded record.
- Never persist a full Employee reply, a full sandbox output, a full patch body, or a full file content.
- Never persist environment variables or secret-shaped strings (reuse `output.redact_environment_like_content` on any excerpt derived from tool output).

### 4.5 Tag and keyword derivation — deterministic tokenization

Tags come from a fixed extractor per category. Examples (final choice at implementation time based on what's actually available in each payload):

- `pm_specifications`: `spec:{spec_id}`, `version:{n}`, plus lowercased alphanumeric tokens from the spec title (bounded to first 8).
- `failed_attempts`: `reason_code:{code}` (from Sprint 17), `task:{task_id}`, plus lowercased tokens from the task title.
- `ceo_approvals`: `decision:{approved|rejected|changes_requested}`, `task:{task_id}`.
- `reviewer_feedback`: `outcome:{approved|changes_requested}`, `task:{task_id}`.
- `successful_solutions`: `task:{task_id}`, plus lowercased tokens from the task title.
- `prior_discussions`: `spec:{spec_id}`, `kind:{turn_kind}`, `role:{role_key}`.

`keywords_text` is a lowercased, whitespace-normalized concatenation of the title + salient text fields (bounded ≤ 4096 chars). Substring match happens against this field, so it must contain what a PM would search for.

Tokenization is pure Python (`.lower().split()`, filter non-alphanumeric, dedupe). No NLP dependency, no stemming, no stopword list beyond a small in-code set of trivially-empty tokens (`the`, `a`, `and`, `of`, `to`, `for`, `in`, `on`, `is`, `it`).

### 4.6 EventBus subscriber for real-time projection

On startup (in `main.py::lifespan`, after `event_bus` is constructed), subscribe one handler per projected `EventType`. Each handler:

1. Reads the event's structured payload.
2. Runs the category's extractor (pure function).
3. If the extractor returns `None` (e.g. the event's payload is malformed or missing a required field), do nothing — never raise, log at INFO.
4. Otherwise, inserts a `MemoryRecordORM` row. On `IntegrityError` from `UNIQUE(source_event_id)`, do nothing — this is a duplicate (real-time raced with backfill), which is the correct outcome; log at DEBUG.
5. After a successful insert, publish `memory.recorded` (tiny payload — see §4.9).

Handlers run inline in `event_bus.publish` (in-process EventBus, unchanged from Sprint 3 tradeoff). Publish latency delta is bounded by the extractor's own cost (small, no I/O beyond one INSERT).

### 4.7 Idempotent backfill

Add `apps/api/app/modules/memory/backfill.py::backfill_memory(session_factory, event_bus, project_id=None)` — an async routine that iterates all persisted events (or all events for a given project) and calls the same extractors as the subscriber. Because `UNIQUE(source_event_id)` is DB-enforced, re-running backfill is safe: existing records survive, new events get projected once.

Backfill is **not** wired into `lifespan` automatically. It is exposed as `scripts/backfill_memory.py` for a one-shot operator run and as a testable service function. Rationale: existing Companies with a large event history should not pay the projection cost on every boot; the operator triggers it once when the memory module is enabled.

### 4.8 Recall — PM explicitly requests it, deterministic ranking

Extend the PM's planning JSON contract with **one new optional field**: `recall_request`. Every existing PM turn kind (`pm_analysis`, `pm_draft_or_followup`, `pm_draft`, `pm_revision_draft`) may now include this field in its response:

```json
{
  ... existing PM turn fields ...
  "recall_request": {
    "categories": ["failed_attempts", "reviewer_feedback"],   // optional; default: all six
    "tags": ["auth", "session"],                              // optional; each ≤ 64 chars, max 16
    "keywords": ["login", "password"],                        // optional; each ≤ 64 chars, max 16
    "since_days": 90,                                         // optional; server-capped at MAX_RECALL_LOOKBACK_DAYS
    "limit": 5                                                // optional; server-capped at MAX_RECALL_LIMIT
  }
}
```

Behavior when the field is present:

1. `PlanningOrchestrator` calls `memory.service.recall(project_id, request)` deterministically between the PM turn that emitted the field and the next scheduled turn.
2. `recall` returns a bounded list of `RecalledMemory` items (id, category, title, tags, created_at, small `preview` extracted from `content_json`).
3. The orchestrator serializes the results as a small structured user message (JSON block, well-formatted) and appends it to `messages` before the next turn.
4. `memory.recalled` event is published (tiny payload).

Behavior when the field is absent or `null`: **nothing happens.** The planning turn proceeds exactly as it did in Sprint 12. This is what "PM explicitly requests" means — the field's presence is the trigger, no other path fires recall.

The CTO's contract is **not** extended. Only the PM may recall in Sprint 18. Extending recall to the CTO or to the Engineer's harness is a future-sprint decision.

### 4.9 Ranking — deterministic arithmetic

`memory.service.recall` scores each candidate record by:

```
score = (tag_matches + keyword_matches) * recency_decay
```

Where:

- `tag_matches`: count of query `tags` that appear in the record's `tags` list (exact match after lowercasing).
- `keyword_matches`: count of query `keywords` (each lowercased) that appear as substrings in the record's `keywords_text`.
- `recency_decay`: a deterministic function of age in days. Suggested: `exp(-age_days / HALF_LIFE_DAYS)` where `HALF_LIFE_DAYS = 30`. Never zero; never negative; monotonic in age. If `exp` feels heavy for this, `1.0 / (1.0 + age_days / HALF_LIFE_DAYS)` is acceptable — pick one, document the choice, do not switch mid-implementation.

Sort: `score desc`, `created_at desc`, `id asc`. This ordering is fully deterministic — the same query against the same DB always returns the same list.

If both `tags` and `keywords` are empty, `score = recency_decay` alone (most recent within `since_days` wins). Records with `score == 0` (no matches AND `since_days` excludes them) are omitted.

Total returned records are capped at `min(request.limit, MAX_RECALL_LIMIT)`. `MAX_RECALL_LIMIT = 10` — a PM asking for 100 gets 10; a PM asking for 3 gets 3.

### 4.10 Recall bounds — server-enforced ceilings

Server enforces the following, regardless of what the PM's JSON asks for:

```
MAX_RECALL_LIMIT = 10
MAX_RECALL_LOOKBACK_DAYS = 365
MAX_TAG_COUNT = 16
MAX_TAG_LENGTH = 64
MAX_KEYWORD_COUNT = 16
MAX_KEYWORD_LENGTH = 64
```

Any request field exceeding a cap is silently truncated to the cap (not rejected — a well-meaning PM asking for `limit=100` should still get useful results, not a hard error). Malformed types (`tags = "auth"` instead of `["auth"]`) are rejected via Pydantic validation and the recall silently returns an empty list; the orchestrator logs a warning and continues the turn without injecting any recall results.

`categories` field: only the six valid category strings are honored; unknown values are silently dropped.

### 4.11 Category filter defaulting

If `categories` is `null` or absent in the request, recall searches **all six categories**. If it is an empty list `[]`, recall returns an empty result set (interpreted as "the PM explicitly asked for no categories"). Document this distinction in the PM contract text so an ambiguous PM output does not silently produce an unexpected search.

### 4.12 Timeline events — two new, tiny payloads

Add exactly two new `EventType` values:

```
MEMORY_RECORDED = "memory.recorded"
MEMORY_RECALLED = "memory.recalled"
```

Payloads:

- `memory.recorded`: `{memory_id: str, category: str, source_event_id: str, source_task_id: str | None, source_specification_id: str | None}`. No title, no content, no keywords. Actor: `system`. Reason: `f"Projected {category} from event {source_event_id[:8]}"`.
- `memory.recalled`: `{spec_id: str | None, requested_categories: list[str], match_count: int, memory_ids: list[str]}`. No preview text, no keyword echo. Actor: PM's `Actor` (role `employee`, id/name from the resolved PM). Reason: `f"PM recalled {match_count} memory record(s)"`.

Both are `kind = "system"`. Neither leaks record contents. They exist so the CEO's Timeline shows "Memory is happening" without exposing what — a Sprint 19+ UI can render them if it chooses.

### 4.13 No public API, no dashboard change

Backend:

- No new HTTP endpoint. Memory is internal PM context only.
- No new field on `GET /api/tasks/{id}/harness-summary` (unrelated concept).
- No extension of `GET /api/projects/{id}/workspace/overview` (Sprint 19+ decision if desired).

Frontend:

- **No new widget, no MissionDetail change, no CEO Workspace shell change, no new page or route.**
- The only allowed frontend change is regenerating TS event schemas (`python scripts/generate_ts_schemas.py`) so `MEMORY_RECORDED` and `MEMORY_RECALLED` are known event types in `packages/event-schemas/ts/`. If a TypeScript compile error follows, fix the type; do not render the new events anywhere.

Rationale: Sprint 16 and Sprint 17 both landed backend-only with no CEO-facing surface, deliberately (DECISIONS.md #238, #242). Memory follows the same pattern. A CEO-facing Memory surface is a legitimate Sprint 19+ product decision, tied to the eventual PM-conversation-plus-Widget-Dock layout in UX_SPEC §3.

### 4.14 Company-scoped only, project ownership discipline

Every recall call, every projection insert, every `memory.recorded`/`memory.recalled` event carries a single `project_id`. There is no code path that reads or writes a Memory record whose `project_id` differs from its caller's project scope. The Sprint 15/16 ownership discipline (`resource_owned_by` returning 404) is not directly needed here because there is no public route — but if any future sprint adds one, the pattern must be applied.

### 4.15 Load-bearing rule — Memory is a projection, never a truth source

**The one rule this sprint hinges on:**

> **Memory records are always derivable from events. If a Memory row disagrees with an event, the event wins. If Memory is wiped, backfill reconstructs it byte-for-byte.**

This is Rule #14 restated in this sprint's terms. It means:

- The subscriber never rewrites history — it only projects future events (and the backfill idempotently catches up).
- No mutation API exists on Memory records — no `PUT`, no `PATCH`, no "edit this record."
- If an extractor is later changed, the operator re-runs backfill; races are safe (UNIQUE dedup).
- If a Memory record ever has a field the source event doesn't support, the extractor is buggy — fix the extractor, do not fix the record in place.

---

## 5. Architecture Requirements

Prefer boundaries equivalent to:

- New module `apps/api/app/modules/memory/`:
  - `registry.py` — the six category strings + tag-extractor rules (frozen, code-owned).
  - `schemas.py` — `MemoryRecord` Pydantic response, `RecallRequest` Pydantic (parsed from PM's JSON field), `RecalledMemory` result item.
  - `projection.py` — one extractor function per projected `EventType` (`extract_from_task_failed(event) -> MemoryRecord | None`, etc.). Pure functions of the event's payload plus `project_id`. Zero I/O.
  - `service.py` — `record_memory(session_factory, event_bus, event) -> MemoryRecord | None` (called by the subscriber), `recall(session_factory, project_id, request) -> list[RecalledMemory]` (called by the planning orchestrator).
  - `subscriber.py` — one wiring function that subscribes handlers for every projected `EventType`. Called from `main.py::lifespan`.
  - `backfill.py` — `backfill_memory(session_factory, event_bus, *, project_id=None)` — idempotent one-shot projector over persisted events.
- `apps/api/app/core/db_models.py`: new `MemoryRecordORM` per §4.3.
- `apps/api/app/core/events/types.py`: `MEMORY_RECORDED`, `MEMORY_RECALLED` added.
- `apps/api/app/core/events/contracts.py`: payload models for both events.
- `apps/api/app/modules/planning/orchestrator.py`: `_VALIDATORS` for every PM turn kind extended to accept an optional `recall_request` field; the loop calls `memory.service.recall(...)` between turns when present.
- `apps/api/app/templates/software_company.py`: `_PM_PLANNING_CONTRACT` extended to document the new `recall_request` field the PM may emit. No change to `_CTO_PLANNING_CONTRACT`.
- New Alembic migration on top of `b1f4c8d5e9a2`.
- `scripts/backfill_memory.py` — thin CLI wrapper.

The memory module is **not** allowed to:

- import from `agent_harness`, `workflow_engine`, `tasks`, or `approvals` directly (Rule #1 — it reads events from shared `core.events`; if it needs a Task, it goes through the `TaskORM` shared floor via a session query, not a service import).
- call `ProviderGateway` (Rule #4 — no LLM in projection or recall).
- read the workspace or sandbox.
- write events other than `memory.recorded` / `memory.recalled`.

`memory.service.recall` is a plain async function called by `PlanningOrchestrator` — do not construct a `MemoryService` singleton in `lifespan`; the "no dedicated service DI" pattern of `tasks/service.py` and `planning/service.py` applies here too.

---

## 6. Persistence and Audit

- One new table (`memory_records`), one new migration. Verify upgrade/downgrade round-trip against real Postgres.
- Fresh-bootstrap via `scripts/seed.py` must succeed end-to-end (drops schema, replays all migrations from base through this new head).
- `UNIQUE(source_event_id)` is the deduplication guarantee (not application-level check-then-insert).
- No new columns on any existing table.
- The audit trail for Memory is the Memory table itself + the two new events. There is no need to extend `HarnessToolCallORM` or any other audit table.

---

## 7. Planning Integration (Sprint 12 extension)

`PlanningOrchestrator._run`'s per-turn dispatch (the `while` loop in `orchestrator.py`) is where recall integrates. Concretely:

1. After each PM turn's JSON is parsed and validated, check for `recall_request` in the parsed dict.
2. If present and non-null, call `memory.service.recall(session_factory, project_id, recall_request)`.
3. Format the returned `list[RecalledMemory]` as a small structured JSON block (see §4.8), prefixed by a short server-owned reminder text like `"Memory recall results (deterministic, keyword+tag+recency match):"`.
4. Append it as one user-role message to `messages` before the next `gateway.complete(...)` turn.
5. Publish `MEMORY_RECALLED` via `event_bus.publish(...)` (tiny payload per §4.12).
6. Even if the result list is empty, still publish the event (so a PM asking recall with zero hits is still observable). The user-message injection is skipped if the result list is empty (do not inject an empty "no results" block that would waste turn tokens).

The CTO's turn kinds (`cto_review`, `cto_followup_answer`) do **not** grow a `recall_request` field. Only PM turn kinds. Do not extend `_CTO_PLANNING_CONTRACT`.

`recall_request` must be optional in all PM validators. A PM response without the field is unchanged from Sprint 12 behavior. A PM response with `recall_request: null` is treated identically to absence.

---

## 8. API and Dashboard Scope

Backend:

- **No new public HTTP endpoint.** Memory is internal to the planning pipeline. No `POST /api/memory/recall`, no `GET /api/memory/records`, no admin route.
- The two new events flow through the existing SSE stream automatically once registered and TS schemas regenerated.

Frontend — **no UI changes this sprint.** Explicit:

- **No new widget.** Do not add a `MemorySummary` widget or any widget to `workspace_widgets/registry.py`.
- **No `MissionDetail.tsx` change.** Do not surface Memory in any mission view.
- **No `SpecificationDetail.tsx` change.** Do not surface recalled memories in the specification transcript.
- **No CEO Workspace shell change, no new page, no new route.**
- **The only allowed frontend change:** regenerate TS event schemas (`python scripts/generate_ts_schemas.py`) so `MEMORY_RECORDED` and `MEMORY_RECALLED` types compile. If a TypeScript compile error follows the regeneration, fix the type; do not render the events anywhere.

Rationale: Sprint 16 and 17 shipped backend-only. Memory is deliberately internal PM context for this sprint. A CEO-facing Memory surface is a legitimate follow-up sprint tied to UX_SPEC §3's PM-conversation-plus-dock layout, not a Sprint 18 bolt-on.

---

## 9. Required Behavioral Tests

Add tests following existing patterns (`test_agent_harness_*`, `test_planning_*`, `test_event_bus.py`, `test_specification_orm_constraints.py`, `test_workspace_service.py`):

### Projection (per category)
- `TASK_FAILED` with `reason_code="self_correction_exhausted"` (Sprint 17) projects a `failed_attempts` record with the right tags (`reason_code:self_correction_exhausted`, `task:<task_id>`) and title tokens.
- `TASK_FAILED` with `reason_code="employee_surrendered"` projects a `failed_attempts` record with the surrender-specific `reason_code` tag and the bounded surrender text as a `preview` field.
- `TASK_FAILED` without a `reason_code` (pre-Sprint-17 generic failures) still projects a `failed_attempts` record with a default reason string.
- `TASK_COMPLETED` projects a `successful_solutions` record with `code_stats` summary and `check_results` pass/total counts.
- `APPROVAL_GRANTED` / `APPROVAL_REJECTED` / `APPROVAL_CHANGES_REQUESTED` each project a `ceo_approvals` record with the right decision tag.
- `SPECIFICATION_APPROVED` projects a `pm_specifications` record with structured goals/requirements/acceptance_criteria.
- `REVIEW_COMPLETED` projects a `reviewer_feedback` record with the bounded four sections.
- `SPECIFICATION_TURN_POSTED` projects a `prior_discussions` record with the bounded text excerpt.
- Every projected record has non-empty `tags` and `keywords_text`.
- Every excerpt in `content_json` is under its per-field cap; no full Employee reply survives.

### Extractor safety
- An event with a malformed payload (missing required field) returns `None` from the extractor, does not raise, does not insert.
- An event with a null field where a string is expected does not raise.
- `redact_environment_like_content` is applied to any excerpt derived from tool output (only for the categories where that is a real source — most extractors read structured payloads, but `failed_attempts` may include Employee surrender text).
- An oversized text field triggers the drop-and-mark-truncated behavior (`_truncated: true` in `content_json`).

### Deduplication
- Subscribing to the same event twice writes exactly one record.
- Backfill run twice writes each record exactly once.
- Subscriber and backfill racing (concurrent) never produce duplicate records; the second insert catches `IntegrityError` and continues.
- Re-projecting the same event via `record_memory(...)` explicitly returns the existing record (or None), never duplicates.

### Subscriber isolation
- A projection extractor that raises does not break `EventBus.publish`; the event still fans out to other subscribers.
- A projection insert failure is logged and swallowed; the publish still succeeds.

### Recall
- Empty recall query (`recall_request: {}`) returns most-recent records across all six categories, bounded by `MAX_RECALL_LIMIT`.
- Query with `categories=["failed_attempts"]` returns only that category.
- Query with `categories=[]` returns empty list.
- Query with unknown category strings silently drops them.
- Tag-only query ranks records with more tag matches first.
- Keyword-only query ranks records with more keyword matches first.
- Tag + keyword combined query sums matches.
- Same score → most recent first → tie-break by id ascending.
- `since_days` filter honored; records older than the cutoff excluded.
- `limit=100` is capped at `MAX_RECALL_LIMIT`; `limit=3` returns at most 3.
- Malformed `tags = "auth"` (string, not list) parses as empty list; recall does not crash.
- Recall over an empty Memory returns empty list, not error.
- Recall in a project with only other-project records returns empty list (project scoping).
- Recall never returns records whose `project_id` differs from the query's `project_id`.

### Backfill
- Backfill over a project with N events produces N valid Memory records (only for the projected event types among them).
- Backfill over an empty event stream is a no-op.
- Backfill with an existing partial Memory table completes the gap without duplicating existing records.
- Backfill can be scoped to `project_id=None` (all Companies) or a specific project.

### Planning integration
- A PM turn's JSON with no `recall_request` field behaves identically to Sprint 12 baseline — all existing planning tests unchanged.
- A PM turn with `recall_request: null` behaves identically to no field.
- A PM turn with a valid `recall_request` triggers a recall between turns and injects a bounded structured user message before the next turn.
- The injected message is a JSON block, deterministic, size-bounded.
- A PM turn with `recall_request` and zero matching records publishes `MEMORY_RECALLED` with `match_count=0` but injects no user message.
- The CTO's turn kinds do not accept `recall_request` (validator rejects it if present).
- A CTO turn's JSON with `recall_request` produces a validation error and follows the existing `MAX_MALFORMED_ATTEMPTS` path (unchanged Sprint 12 behavior).

### Timeline events
- Every successful projection publishes `memory.recorded` with the correct tiny payload.
- Every recall (including empty-result) publishes `memory.recalled` with the correct tiny payload.
- Neither event's payload carries any content body.

### Migration
- `alembic upgrade head` on a fresh Postgres applies the new migration cleanly.
- `alembic downgrade -1` cleanly reverts (drops the table with no orphan constraints).
- `alembic history` shows a single linear chain with the new head at the top.

### Regression
- Full backend suite passes; `test_planning_orchestrator.py`, `test_planning_api.py`, `test_code_missions.py`, `test_reliability.py`, `test_agent_harness_*` all green with zero modifications.
- Role-hardcoding AST guard (`test_role_hardcoding_guard.py`) remains green (no new role-name literals).
- Mock E2E with zero provider keys still passes; add one new scenario that exercises PM recall end-to-end deterministically.

---

## 10. Phases

### Phase 0 — Baseline verification and architecture decisions

1. Verify HEAD, origin/master, working tree clean.
2. Run backend baseline (`pytest apps/api`). Confirm 472 passed / 6 skipped.
3. Run dashboard `tsc --noEmit` and `next build`. Confirm all 19 routes.
4. Verify Alembic head is `b1f4c8d5e9a2` and migration round-trip is clean.
5. Run a mock code Mission end-to-end with zero provider keys (existing tests already cover this — confirm they pass).
6. Read every file listed in §3.
7. Inventory every `EventType` currently emitted and confirm which of §4.1's six sources exist in the codebase (they all should).
8. Inspect `event_bus.subscribe(...)` — how many existing subscribers exist, what pattern they follow.
9. Decide the exact tokenizer and stopword list for `keywords_text` / `tags`. Record.
10. Decide the exact recency-decay formula (`exp` vs simple decay). Record.
11. Decide `MAX_RECALL_*` constants (defaults per §4.10) — adjust only if the code inspection suggests different bounds are safer.
12. Decide the exact ORM shape for `MemoryRecordORM` and the migration name.
13. Confirm the projected event list matches §4.1 by cross-referencing what `EventType` values exist today.
14. Replace/append PROGRESS.txt with Sprint 18 live checklist.
15. Record non-obvious decisions in DECISIONS.md (new entries starting at #243).
16. Commit/push Phase 0 checkpoint.

### Phase 1 — Memory table, ORM, migration, projection module, subscriber wiring

1. Add `MemoryRecordORM` to `core/db_models.py` per §4.3.
2. Create Alembic migration on top of `b1f4c8d5e9a2`; verify upgrade/downgrade round-trip locally against real Postgres.
3. Create `apps/api/app/modules/memory/` with `__init__.py`, `registry.py`, `schemas.py`, `projection.py`, `service.py`, `subscriber.py` skeletons.
4. Implement `registry.py`: the six category strings + tag-extractor rule map.
5. Implement `schemas.py`: `MemoryRecord`, `RecallRequest`, `RecalledMemory` Pydantic models with the caps in §4.10 baked in (`Field(max_length=..., max_items=...)`).
6. Implement `projection.py`: one pure-function extractor per projected `EventType`. Each returns a small structured dict / `None` — no I/O.
7. Implement `service.record_memory(session_factory, event_bus, event)`: runs extractor, inserts row, catches `IntegrityError` on `source_event_id` UNIQUE, publishes `MEMORY_RECORDED` on real insert.
8. Add `MEMORY_RECORDED` and `MEMORY_RECALLED` to `core/events/types.py` and their payload models to `core/events/contracts.py`.
9. Implement `subscriber.py::install_memory_subscribers(event_bus, session_factory)` that registers one handler per projected `EventType`.
10. Wire the subscriber install into `main.py::lifespan` after `event_bus` is constructed and before orphan recovery.
11. Unit tests: extractor correctness per category (fixture events), extractor safety (malformed payloads → None), record_memory dedup, subscriber isolation (raising extractor does not break publish).
12. Update PROGRESS.txt.
13. Commit/push Phase 1.

### Phase 2 — Recall service + PM contract extension + planning integration

1. Implement `service.recall(session_factory, project_id, request) -> list[RecalledMemory]` per §4.9 ranking. Enforce every §4.10 cap server-side.
2. Extend `PlanningOrchestrator._VALIDATORS` for every PM turn kind (`pm_analysis`, `pm_draft_or_followup`, `pm_draft`, `pm_revision_draft`) so `recall_request` is an optional field with strict Pydantic-style validation.
3. Update `_PM_PLANNING_CONTRACT` in `templates/software_company.py` to document the new field and its semantics.
4. Extend `PlanningOrchestrator._run` to detect the field on any PM turn, call `memory.service.recall`, format results as a bounded structured user message per §7 item 3, append to `messages`, publish `MEMORY_RECALLED`.
5. Explicitly reject `recall_request` on CTO turn kinds via the existing validator path.
6. Unit tests: recall ranking (tags, keywords, recency, ties), server cap enforcement, empty query, malformed query, project scoping.
7. Integration tests: PM planning run with `recall_request` field injects a formatted user message; PM run without the field is unchanged; CTO run with the field fails validation like any other malformed CTO output.
8. Update PROGRESS.txt.
9. Commit/push Phase 2.

### Phase 3 — Backfill + Sprint 17 signal projection + mock recall scenario

1. Implement `backfill.py::backfill_memory(session_factory, event_bus, *, project_id=None)`.
2. Add `scripts/backfill_memory.py` — small CLI wrapper (`python -m scripts.backfill_memory --project-id ...` or all-companies).
3. Verify Sprint 17's `TASK_FAILED.reason_code` payload projects correctly to `failed_attempts` records with the right tags and preview.
4. Verify the extraction of `EmployeeSurrenderedError`-derived `TASK_FAILED` events preserves the bounded surrender text as `preview` (never raw).
5. Add one mock planning scenario (marker in the PM's initial request text, mirroring Sprint 17's `SELF_CORRECTION_DEMO` convention) that: (a) plants a few Memory records via fixture, (b) drives the PM to include a `recall_request` in `pm_analysis`, (c) asserts the recall runs, publishes the event, and injects a user message before the CTO turn.
6. Backfill integration test: create N events, empty Memory, run backfill, assert one record per projected event, no duplicates on re-run.
7. Regenerate TS event schemas (`python scripts/generate_ts_schemas.py`).
8. Update PROGRESS.txt.
9. Commit/push Phase 3.

### Phase 4 — Regression, security audit, documentation, and close-out

1. Run full backend suite. Target: 472 baseline + Sprint-18 new tests, zero regressions outside Sprint 18 files.
2. Run dashboard `tsc --noEmit` + `next build`. Confirm regenerated event types compile.
3. Verify migration chain via `alembic heads`/`history` and a real Postgres round-trip through `scripts/seed.py`.
4. Run mock E2E with zero provider keys covering the new recall scenario.
5. Run existing planning / specification / mission / workspace / widget / harness / self-correction regressions.
6. Independent security audit (dedicated read-only agent, not self-audit):
   - Every extractor is pure and I/O-free.
   - No projection or recall path calls `ProviderGateway`.
   - Recall never returns a record whose `project_id` differs from the query's.
   - `UNIQUE(source_event_id)` is DB-enforced, not application-level check-then-insert.
   - Every excerpt uses `bound_output`; no full Employee reply, no full sandbox output, no full patch body survives.
   - `redact_environment_like_content` is applied to any excerpt derived from tool output.
   - `MEMORY_RECORDED` / `MEMORY_RECALLED` payloads carry no content bodies.
   - No public HTTP endpoint exposes recall or Memory records.
   - The subscriber never raises into `EventBus.publish`.
   - Server-enforced caps (`MAX_RECALL_LIMIT`, `MAX_RECALL_LOOKBACK_DAYS`, `MAX_TAG_COUNT`, etc.) apply regardless of PM request.
   - CTO turns cannot request recall.
   - Role-hardcoding guard clean.
7. Inspect the full diff for scope leakage (RAG/vector, cross-Company, Employee memory tool, CEO-facing UI, cross-Mission autonomous learning).
8. Documentation sync:
   - `CLAUDE.md` roadmap row 18 → "18 ✅".
   - `docs/ARCHITECTURE.md` §5 rewritten to match as-built Memory (was written as intended target; must now describe reality per Rule #10). §6 module table gains a `memory` row.
   - `docs/DECISIONS.md` new entries #243+ covering the recall-explicit-only choice, deterministic-only projection, event-source category mapping, ranking formula, server caps, no-UI stance, and any non-obvious phase decision.
   - `README.md` status paragraph updated only if a CEO-facing user-visible change landed (should not).
   - `docs/design/UX_SPEC.md` updated only if any dashboard change landed (should not).
   - `FOR_CTO.md` §5 (Domain Model — add MemoryRecord), §6 (Planning — add PM recall extension), §8 (Events — add memory.recorded/recalled), §12 (Decisions — add Memory decisions), §13 (Invariants — add "Memory is projection only"), §14 (Critical Files — add memory module paths), §18 Sprint 18 handover, §19 CTO Warnings.
9. Record residual limitations honestly (e.g. "keyword substring match is naïve — no stemming, no fuzzy match — deliberate for Sprint 18", "no cross-Company memory", "no vector recall — future sprint", "no CEO-facing surface — future sprint tied to UX_SPEC §3").
10. Record Sprint 19 boundaries and deferrals in DECISIONS.md close-out entry.
11. Final commit / push.
12. Verify clean working tree.
13. Verify local HEAD == origin/master.

---

## 11. Definition of Done

Sprint 18 is complete only when:

1. Baseline is verified before any code change (472 passed / 6 skipped, dashboard typecheck/build green, Alembic head `b1f4c8d5e9a2`).
2. New table `memory_records` exists with the shape in §4.3.
3. New Alembic migration on top of `b1f4c8d5e9a2` applies cleanly and round-trips downgrade/upgrade on real Postgres.
4. `UNIQUE(source_event_id)` is DB-enforced.
5. `MemoryRecordORM` follows the existing ORM shape convention (see `HarnessToolCallORM` for precedent).
6. All six §4.1 categories have working extractors registered on the corresponding `EventType`.
7. Every extractor is a pure function of the event's structured payload plus `project_id`; no I/O, no LLM call.
8. Excluded categories (`architecture_decisions`, `coding_conventions`) are explicitly documented as deferred, not silently ignored.
9. Conversation events (`CONVERSATION_MESSAGE`, `CONVERSATION_MESSAGE_DELTA`) are NEVER projected.
10. Every projected record has non-empty `tags` and `keywords_text` derived deterministically.
11. Every excerpt in `content_json` is bounded via `bound_output` with an explicit low cap; `redact_environment_like_content` is applied to tool-output-derived excerpts.
12. Oversized fields trigger drop-and-mark (`_truncated: true`) rather than persist unbounded.
13. Subscriber installed in `main.py::lifespan`, one handler per projected `EventType`.
14. Subscriber never raises into `EventBus.publish` (log-and-swallow pattern).
15. Extractor returning `None` for a malformed event is silent (INFO log at most), never raises.
16. `record_memory` catches `IntegrityError` on the dedup constraint and continues silently.
17. `backfill_memory` is idempotent and can run repeatedly without duplicates.
18. `scripts/backfill_memory.py` exposes the backfill as a CLI operator action.
19. `MEMORY_RECORDED` and `MEMORY_RECALLED` `EventType` values exist and are registered with tiny payloads per §4.12.
20. Neither event's payload carries a content body.
21. PM planning contract (`_PM_PLANNING_CONTRACT`) documents the optional `recall_request` field.
22. `PlanningOrchestrator._VALIDATORS` accept an optional `recall_request` on every PM turn kind.
23. CTO turn kinds reject `recall_request` via existing validation.
24. Recall is called by the orchestrator only when the PM's parsed JSON contains a non-null `recall_request`.
25. Recall never runs automatically anywhere else — not in `_run_pipeline`, not in `_run_engineer_tool_loop`, not from any HTTP route.
26. Ranking is deterministic per §4.9; same query against same DB always returns same list.
27. Server-enforced caps (`MAX_RECALL_LIMIT = 10`, `MAX_RECALL_LOOKBACK_DAYS = 365`, `MAX_TAG_COUNT = 16`, `MAX_TAG_LENGTH = 64`, `MAX_KEYWORD_COUNT = 16`, `MAX_KEYWORD_LENGTH = 64`) apply regardless of PM request.
28. Malformed recall request (wrong types) is handled gracefully (empty recall + warning log), does not crash the planning turn.
29. Recall over an empty Memory returns `[]`, not error.
30. Recall is Company-scoped — no record with a different `project_id` is ever returned.
31. Recall path never calls `ProviderGateway`.
32. Projection path never calls `ProviderGateway`.
33. Sprint 17's `TASK_FAILED.reason_code` (self_correction_exhausted / employee_surrendered) projects correctly to `failed_attempts` records with the right tags and bounded preview.
34. Sprint 12's `SPECIFICATION_APPROVED` projects correctly to `pm_specifications`.
35. Existing `APPROVAL_*`, `REVIEW_COMPLETED`, `TASK_COMPLETED`, `SPECIFICATION_TURN_POSTED` events all project correctly.
36. Default planning flow (no `recall_request`) is byte-for-byte equivalent to Sprint 12/17 baseline — zero modifications to existing planning tests, all pass unchanged.
37. Full backend suite passes (472 baseline + new tests, zero regressions outside Sprint 18 files).
38. Dashboard `tsc --noEmit` + `next build` pass after TS schema regeneration.
39. **No new widget, no `MissionDetail.tsx` change, no `SpecificationDetail.tsx` change, no CEO Workspace shell change** (§8).
40. **No new public HTTP endpoint** (backend or admin route).
41. Full mock E2E with zero keys passes covering the new recall scenario.
42. Existing planning / specification / mission / workspace / widget / harness / self-correction behavior remains functional.
43. Independent security audit finds zero CONCERN/FAIL items across the §10 Phase 4 audit list.
44. `CLAUDE.md` (roadmap row 18 → "18 ✅"), `docs/ARCHITECTURE.md` §5 (rewritten as-built), `docs/DECISIONS.md` (#243+), `FOR_CTO.md` (§5/§6/§8/§12/§13/§14/§18/§19) synchronized in the same commits as the code.
45. No Sprint 19+ scope (RAG/vector, cross-Company, Employee-memory tool, autonomous cross-Mission learning, CEO-facing Memory surface, production/deployment hardening) leaked into the diff.
46. Residual limitations recorded honestly (deterministic-only ranking, no stemming/fuzzy match, no cross-Company recall, no vector, no CEO-facing UI).
47. Final commits pushed.
48. Local HEAD equals origin/master.

Do not claim browser verification unless a browser was actually used. Sprint 16/17-style "UNVERIFIED, no CEO-facing UI change this sprint" is the correct honest classification for Sprint 18 (per §8's hard no-UI decision).

---

## 12. Out of Scope

Do not implement:

- RAG, vector embeddings, semantic search, or any similarity-scored recall (future sprint).
- Any LLM call inside projection or recall.
- Cross-Company memory (memory is `project_id`-scoped only).
- Cross-Mission autonomous learning (recall is PM-explicit only; nothing fires automatically).
- Employee-side (Engineer/Reviewer/CTO harness) recall tools.
- Auto-fix or auto-inject-context into `_run_engineer_tool_loop` based on prior failure records.
- Reviewer-driven memory (Reviewer requesting recall from prior missions).
- Public HTTP recall API of any kind.
- Admin/operator API beyond the CLI backfill script.
- New CEO-facing UI (widget, page, MissionDetail extension, SpecificationDetail extension, Timeline rendering of memory events).
- LLM-generated memory summaries (deterministic projection only).
- Deletion, editing, or curation of memory records (append-only, immutable).
- Cross-project memory search (a PM in Company A cannot recall from Company B).
- Categories beyond the six named in §4.1 (`architecture_decisions`, `coding_conventions` deferred).
- Projection of conversation events (`CONVERSATION_MESSAGE`, `CONVERSATION_MESSAGE_DELTA`).
- Extending the CTO's planning contract to request recall.
- Production/deployment hardening (Sprint 19).
- Any change to Sprint 16 harness authorization, Sprint 17 self-correction, or the Sprint 15 widget system.

If a Sprint 19+ need appears mid-implementation, record it as a follow-up in `PROGRESS.txt`'s handoff notes — do not implement it here.

---

## 13. Final Report

Return one evidence-based report containing:

1. Starting / final / origin SHA and working-tree state
2. Sprint result and DoD checklist count (48 items)
3. Commits and their rationale
4. Any repository divergences discovered
5. Security model (delta from Sprint 17 §2)
6. Memory data model — table shape, category mapping, extractor rules, dedup guarantee
7. Projection design — pure-function extractors, subscriber wiring, backfill idempotence
8. Recall design — PM-explicit trigger point, deterministic ranking, server caps
9. Planning integration — how `recall_request` flows through `PlanningOrchestrator._run`
10. Bounds and truncation — every cap that limits stored/returned data
11. Migration — upgrade/downgrade round-trip evidence on real Postgres
12. Verification matrix — baseline → post-Phase-N test counts, dashboard typecheck/build, mock E2E
13. Starting/ending test counts and modified-test classification
14. Existing-feature compatibility — planning, specifications, missions, workspace, widgets, harness, self-correction all green
15. Security audit results with file/line evidence
16. Timeline event payload safety — no bodies, no keywords echo
17. Sprint 17 signal projection — TASK_FAILED.reason_code correctly captured in `failed_attempts`
18. Documentation updates (CLAUDE.md, ARCHITECTURE.md §5, DECISIONS.md #243+, FOR_CTO.md; README/UX_SPEC only if user-visible changes landed)
19. Residual risks and low-confidence areas (naïve substring match, no stemming, no cross-Company, no vector, no CEO-facing surface)
20. Scope control and Sprint 19 handoff
21. Final state (clean tree, HEAD == origin/master)

Begin with Phase 0 and continue through Phase 4 without routine confirmation.
