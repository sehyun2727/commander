# Sprint 13 — CEO Workspace Backend and Projection

Execute this sprint autonomously from Phase 0 through Phase 5.

Expected baseline:
- local HEAD: f81cc7a
- origin/master: f81cc7a
- backend baseline: 297 passed / 4 skipped
- dashboard typecheck/build: PASS
- Sprint 11→12 migration and fresh database bootstrap: PASS
- browser verification: UNVERIFIED unless repository evidence says otherwise

Repository and git state are authoritative. Verify all baseline claims first.

Follow the current CLAUDE.md, architecture, decisions, UX specification, security rules, progress discipline, verification standards, and reporting format.

Do not stop for routine confirmation. Stop only for a hard blocker, destructive ambiguity, security/cost exposure, or an irreconcilable architecture decision.

---

## 1. Goal

Build the stable backend contract and projection layer required for the future CEO Workspace.

At the end of Sprint 13, the dashboard must be able to obtain a coherent CEO-facing view of a company through a small number of authoritative APIs rather than reconstructing business state across many unrelated endpoints.

The workspace backend must provide:

1. A coherent company-level workspace snapshot.
2. Current company and project context.
3. Active and recent missions.
4. Planning/specification state.
5. Pending CEO approvals or clarifications.
6. Employee and leadership availability.
7. Recent safe activity.
8. A server-derived next action.
9. Cursor-based incremental updates.
10. Stable deep-link context.
11. Clear degraded/loading/empty/error semantics.
12. Backward compatibility with existing Sidebar pages and APIs.

This sprint builds backend contracts and minimal integration proof.

Do not implement the full responsive CEO Workspace shell, widget system, Agent Harness, self-correction, or memory.

---

## 2. Product Outcome

The CEO should not need to understand internal tables or infer what to do next.

The server should answer:

- What company am I looking at?
- What is currently happening?
- Which mission or specification needs attention?
- Is the system waiting for me?
- Are PM and CTO available?
- What changed recently?
- What is the single highest-priority next action?
- Where should the UI navigate when I choose that action?

The workspace is an operational command view, not a raw database dump.

---

## 3. Required Repository Inspection

Before changing code, inspect at minimum:

- CLAUDE.md
- PROGRESS.txt
- README.md
- docs/ARCHITECTURE.md
- docs/DECISIONS.md, especially Sprint 10–12 decisions
- docs/design/UX_SPEC.md
- git history from Sprint 10 through f81cc7a
- company/project models and routes
- task/mission models, services, routes, and lifecycle
- planning-run and Project Specification models/services/routes
- approval, clarification, revision, rejection, and cancellation flows
- AgentORM/Employee states, RoleSpecs, and employee resolution
- event models, event bus, SSE or polling implementation, and retention behavior
- dashboard API clients, query keys, hooks, Sidebar routes, mission pages, Specification page, and error handling
- current authentication and company-ownership enforcement
- Alembic migrations, including the Sprint 12 circular-FK fix
- mock E2E fixtures and lifecycle tests
- indexes and query patterns used for company-scoped timeline reads

Confirm whether a reusable projection/read-model layer already exists before adding one.

---

## 4. Approved Product Decisions

### 4.1 Workspace is a read model, not a new source of truth

The workspace projection must derive from authoritative domain data:

- company/project
- missions/tasks
- planning runs
- specifications
- decisions/approvals
- Employees
- events

Do not duplicate mutable business truth into an independent workspace database model unless there is a proven performance need and a clear consistency design.

The initial implementation should prefer on-demand projection through a dedicated query service.

### 4.2 One initial company-scoped snapshot

Provide one authoritative company-scoped workspace snapshot endpoint following existing API naming conventions.

The response should include only data required for the CEO Workspace shell and first paint.

Do not return every historical row or full transcripts.

The exact endpoint may adapt to repository conventions, but should be equivalent to:

GET /api/projects/{project_id}/workspace

or the repository’s canonical company equivalent.

### 4.3 Server-derived next action

The server must calculate the CEO’s highest-priority next action.

The frontend must not recreate lifecycle precedence using scattered conditions.

Use a typed action model containing at least:

- action kind
- title
- short explanation
- target resource type
- target resource ID
- route/deep-link target
- urgency or priority
- whether explicit CEO input is required

The next action should be deterministic for the same committed state.

### 4.4 Proposed action precedence

Verify against the actual lifecycle, then implement and document one deterministic policy.

Preferred precedence:

1. CEO clarification required
2. Specification ready for review
3. Revision feedback or retry required
4. Mission decision/approval required
5. Planning or mission failure requiring attention
6. Approved specification ready to begin execution
7. Active planning or mission in progress
8. Company setup requirement, including vacant critical leadership
9. Start a new project or mission
10. No action / monitor activity

Do not invent executable next steps for unsupported product capabilities.

### 4.5 Safe summary, not hidden reasoning

Workspace activity may include:

- status transitions
- safe role/employee summaries
- specification version events
- approval/revision/cancellation results
- mission progress
- error summaries
- selection reasons already approved for observability

Do not expose:

- chain-of-thought
- hidden system prompts
- provider credentials
- internal unrestricted profile contents
- arbitrary tool definitions
- raw provider payloads

### 4.6 Snapshot consistency

A snapshot should not combine incompatible states such as:

- specification shown as pending after committed approval,
- mission shown executable before approval,
- Employee shown idle while an authoritative active assignment says otherwise,
- next action pointing to a resource absent from the response.

Use one database transaction/session boundary where possible and document consistency guarantees.

Do not claim strict point-in-time consistency if the implementation cannot provide it.

### 4.7 Cursor-based incremental updates

Provide a company-scoped cursor/checkpoint based on authoritative event ordering.

The UI must be able to ask for changes after a known cursor.

Requirements:

- stable ordering
- no cross-company leakage
- duplicate-safe client consumption
- explicit behavior for expired/invalid cursors
- bounded page size
- safe event payloads
- deterministic resume semantics

Reuse existing SSE/event infrastructure if suitable. Do not build a second unrelated event transport.

### 4.8 Reconnect and gap recovery

If live updates disconnect or a cursor becomes invalid:

- client can refetch a fresh snapshot,
- no silent permanent stale state,
- duplicate events do not corrupt state,
- reconnect behavior is bounded,
- errors are visible or recoverable.

Sprint 13 requires the backend contract and a minimal frontend proof, not the final Sprint 14 experience.

### 4.9 Deep-link context

Workspace resources must expose stable navigation targets for:

- mission/task
- specification
- approval/decision
- Employees/Organization
- company setup where relevant

Do not encode authority in client-controlled route parameters.

Every target page must continue to validate auth and company ownership server-side.

### 4.10 Backward compatibility

Do not remove existing Sidebar pages or their APIs.

Sprint 12’s standalone Specifications page remains valid.

The workspace projection is additive and prepares consolidation in Sprint 14.

### 4.11 No writes through the generic snapshot

The workspace snapshot endpoint is read-only.

Existing typed domain mutations remain authoritative for:

- clarification answers
- approval
- revision request
- cancellation
- mission start
- hiring
- Employee configuration

Do not introduce a generic `POST /workspace/action` endpoint that dispatches arbitrary action strings.

### 4.12 Performance budget

The snapshot must avoid obvious N+1 query patterns and unbounded history loads.

Set and document reasonable bounds for:

- recent missions
- recent activity
- pending items
- Employee summaries

Add indexes only where supported by observed query patterns.

Do not add a cache until profiling demonstrates need.

---

## 5. Target Contract

Adapt names to existing repository conventions, but the public response should be typed and versionable.

Expected conceptual structure:

- schema_version
- project/company summary
- organization summary
  - leadership roles
  - occupied/vacant status
  - Employee counts
  - busy/idle/error counts
- focus
  - active resource type and ID
  - current lifecycle status
- pending_actions
  - clarification
  - specification review
  - approval/decision
  - failure/setup action
- next_action
- planning summary
  - active planning run
  - current specification version/status
  - unresolved questions count
- mission summary
  - active missions
  - recent missions
  - progress/stage/status
- recent_activity
- event_cursor
- generated_at

Do not expose complete ORM objects.

Prefer explicit public schemas.

Use enum/string values already established by domain models when safe.

If schema evolution support is needed, add a simple explicit `schema_version`; do not build a general version-negotiation framework.

---

## 6. Projection Service

Implement a dedicated company-scoped query/projection service.

Responsibilities:

- load authoritative domain state,
- calculate safe summaries,
- calculate pending actions,
- select deterministic next action,
- produce public schemas,
- enforce bounds,
- produce an event cursor.

It must not:

- mutate domain records,
- run agents,
- invoke providers,
- advance workflows,
- approve decisions,
- start missions,
- become a second WorkflowEngine.

Keep next-action policy separately testable.

---

## 7. API Requirements

Add the smallest coherent endpoint surface.

Required capabilities:

1. Fetch workspace snapshot.
2. Fetch incremental safe activity after a cursor, unless the existing company SSE endpoint already satisfies this cleanly.
3. Resume/reconnect through the existing event mechanism where possible.
4. Return structured errors for:
   - unknown company/project
   - unauthorized access
   - malformed/expired cursor
   - invalid pagination limit
5. Preserve existing domain mutation endpoints.

Every route must enforce existing authentication and company-ownership boundaries.

No workspace response may expose another company’s:

- Employees
- missions
- specifications
- decisions
- events
- IDs that enable unauthorized inference

---

## 8. Minimal Dashboard Integration Proof

Do not build the final Sprint 14 workspace shell.

Add only enough frontend integration to prove the contract.

Required:

- typed API client
- query keys/hooks
- workspace snapshot query
- incremental update or SSE subscription integration
- reconnect/refetch fallback
- loading state
- empty state
- visible error state
- minimal internal/debug or additive overview surface using existing layout conventions
- deep links to existing pages
- global error handling where mutations or connection controls apply

Do not remove or redesign:

- Sidebar
- Specifications page
- Employees page
- existing mission pages
- existing approval flows

If a visible temporary route is added, label it consistently and avoid presenting it as the final Sprint 14 UX.

---

## 9. Concurrency and Consistency Requirements

Review and test:

1. Approval committed while snapshot is being read.
2. Mission created immediately after approval.
3. Planning status changes while events are fetched.
4. Duplicate event delivery.
5. Cursor pagination with equal timestamps.
6. Employee assignment transitions.
7. Cancel/fail transition during projection.
8. Deleted or unavailable target resource.
9. Cross-company cursor reuse.
10. Reconnect after event retention gap.

Event ordering must not depend only on non-unique timestamps.

Use a stable monotonic key, composite cursor, or existing authoritative sequence.

A cursor must be opaque to clients if exposing internal ordering would be unsafe or brittle.

---

## 10. Security Requirements

- Enforce auth and company ownership on every workspace route.
- Treat all route IDs and cursors as untrusted.
- Return safe summaries only.
- Do not expose hidden reasoning or prompt internals.
- Do not expose provider configuration or API keys.
- Do not expose arbitrary skill/tool definitions.
- Prevent cross-company cursor or resource inference.
- Bound pagination and response size.
- Avoid generic action dispatch.
- Preserve existing CSRF/auth conventions.
- Ensure deep links do not bypass authorization.
- Log failures safely without secret-bearing payload dumps.

---

## 11. Phases

## Phase 0 — Baseline and Read-Model Design

1. Verify local HEAD, origin/master, and working tree.
2. Run baseline backend tests.
3. Run dashboard typecheck and build.
4. Verify Sprint 12 migration and fresh seed/bootstrap.
5. Inspect domain lifecycles, APIs, events, SSE, and frontend query architecture.
6. Identify authoritative sources for every proposed workspace field.
7. Identify existing event ordering and retention behavior.
8. Determine the exact snapshot and cursor contracts.
9. Determine next-action precedence.
10. Determine the minimal frontend proof.
11. Audit likely N+1 and indexing risks.
12. Replace PROGRESS.txt with a Sprint 13 live checklist.
13. Record non-obvious decisions.
14. Commit/push the Phase 0 checkpoint if consistent with repository practice.

## Phase 1 — Public Schemas and Projection Policy

1. Define typed public workspace schemas.
2. Add explicit schema version.
3. Implement bounded summary models.
4. Implement pending-action derivation.
5. Implement deterministic next-action policy.
6. Implement safe deep-link targets.
7. Define activity summary serialization.
8. Define event cursor encoding/validation.
9. Add pure/domain tests for:
   - precedence
   - deterministic selection
   - no-action state
   - missing target handling
   - safe serialization
   - cursor round-trip
   - malformed cursor
   - stable ordering
10. Update PROGRESS.txt.
11. Commit/push Phase 1.

## Phase 2 — Projection Service and Workspace API

1. Implement company-scoped projection service.
2. Load snapshot data through bounded queries.
3. Avoid obvious N+1 patterns.
4. Add indexes only when justified.
5. Produce coherent snapshot and cursor.
6. Add workspace snapshot route.
7. Add or extend incremental activity route/SSE support.
8. Enforce auth and ownership.
9. Add structured cursor and limit errors.
10. Implement invalid/expired cursor recovery semantics.
11. Add API/integration tests for:
    - empty company
    - planning
    - clarification
    - specification review
    - approved-ready state
    - active mission
    - failure state
    - organization vacancy
    - cross-company denial
    - bounded result sizes
12. Inspect query count or SQL behavior through the repository’s available tooling.
13. Update PROGRESS.txt.
14. Commit/push Phase 2.

## Phase 3 — Event and Lifecycle Integration

1. Ensure relevant domain transitions emit or map to safe workspace activity.
2. Verify specification, approval, revision, cancellation, mission, and Employee transitions.
3. Implement stable incremental ordering.
4. Support duplicate-safe consumption.
5. Define reconnect and retention-gap behavior.
6. Ensure next_action changes after authoritative transitions.
7. Verify approval-to-execution readiness.
8. Verify cancellation/failure removes stale actions.
9. Add concurrency/integration tests for:
   - approval during snapshot
   - event fetch during transition
   - duplicate event delivery
   - equal timestamps
   - cross-company cursor
   - retention gap
   - stale target
10. Run an API-level mock lifecycle and capture snapshot/action changes at each stage.
11. Update PROGRESS.txt.
12. Commit/push Phase 3.

## Phase 4 — Minimal Dashboard Contract Proof

1. Add typed workspace client and hooks.
2. Add snapshot query.
3. Add incremental event/SSE integration.
4. Add reconnect/refetch fallback.
5. Add minimal overview/proof surface.
6. Show next action and deep link.
7. Show concise pending, organization, mission, planning, and activity summaries.
8. Implement loading, empty, degraded, and visible error states.
9. Keep existing pages and navigation intact.
10. Avoid recreating next-action precedence in frontend code.
11. Run typecheck.
12. Run production build.
13. Perform browser verification if tooling exists.
14. Otherwise mark browser behavior UNVERIFIED.
15. Update PROGRESS.txt.
16. Commit/push Phase 4.

## Phase 5 — Regression, Audit, and Documentation

1. Run full backend tests.
2. Run dashboard typecheck.
3. Run dashboard production build.
4. Verify migration from Sprint 12.
5. Verify fresh database bootstrap and seed.
6. Run mock E2E with zero provider keys.
7. Verify snapshot states across planning→review→approval→execution.
8. Verify clarification and revision flows.
9. Verify cancellation and failure cleanup.
10. Verify auth and company isolation.
11. Verify cursor resume, duplicate delivery, and gap recovery.
12. Audit response bounds and obvious N+1 behavior.
13. Audit hidden reasoning, secrets, and unsafe metadata.
14. Audit generic-action and mutation leakage.
15. Audit frontend for duplicated lifecycle policy.
16. Inspect complete diff for scope leakage.
17. Update:
    - CLAUDE.md
    - PROGRESS.txt
    - README.md if user/developer workflow changed
    - docs/ARCHITECTURE.md
    - docs/DECISIONS.md
    - docs/design/UX_SPEC.md
18. Record Sprint 14 boundaries and deferrals.
19. Commit/push final documentation.
20. Verify intended clean working tree.
21. Verify local HEAD equals origin/master.

---

## 12. Sprint-Specific Tests

Required behavioral coverage:

- empty workspace
- deterministic next action
- clarification priority
- specification-review priority
- revision/retry priority
- approval priority
- failure/setup priority
- active-progress fallback
- no-action state
- snapshot target consistency
- missing target degradation
- safe public serialization
- bounded mission/activity/Employee summaries
- stable cursor ordering
- equal timestamps
- malformed cursor
- expired cursor recovery
- duplicate event delivery
- reconnect/refetch behavior
- cross-company access denial
- cross-company cursor denial
- approval/snapshot race
- cancellation removes stale action
- failure creates visible attention action
- Employee vacancy/setup action
- approval enables execution readiness
- existing planning, mission, hiring, and specification APIs remain compatible
- mock E2E with zero keys
- Sprint 12 migration upgrade and fresh bootstrap

Do not weaken existing tests merely to make the suite pass.

---

## 13. Definition of Done

Sprint 13 is complete only when:

1. Baseline is verified.
2. Workspace snapshot has an explicit typed public schema.
3. Snapshot derives from authoritative domain data.
4. No independent mutable workspace source of truth is introduced.
5. Snapshot is company-scoped and ownership-protected.
6. Response size is bounded.
7. Obvious N+1 patterns are absent.
8. Pending CEO actions are server-derived.
9. `next_action` is deterministic and documented.
10. Frontend does not duplicate lifecycle precedence.
11. Snapshot contains coherent planning/specification state.
12. Snapshot contains coherent mission state.
13. Snapshot contains safe organization availability.
14. Snapshot contains bounded safe activity.
15. Deep links target existing authorized pages.
16. Event cursor ordering is stable.
17. Equal timestamps cannot reorder or omit events.
18. Incremental updates are company-isolated.
19. Duplicate event delivery is safe.
20. Invalid or expired cursors have explicit recovery behavior.
21. Reconnect can recover through fresh snapshot/refetch.
22. Snapshot/action changes track authoritative transitions.
23. Cancellation and failure remove stale actions.
24. Approval creates execution-readiness state.
25. Existing APIs and Sidebar pages remain functional.
26. Minimal dashboard integration proves the contract.
27. Loading, empty, degraded, and error states exist.
28. No generic workspace mutation dispatcher is added.
29. No hidden reasoning, secrets, or unsafe tool data are exposed.
30. Full backend tests pass.
31. Dashboard typecheck passes.
32. Dashboard production build passes.
33. Sprint 12→13 migration passes, or no migration is accurately reported.
34. Fresh database bootstrap passes.
35. Mock E2E works with zero provider keys.
36. Browser verification is honestly classified.
37. Documentation matches implementation.
38. No Sprint 14+ redesign leaks into the sprint.
39. Final commits are pushed.
40. Local HEAD equals origin/master.

Do not claim complete if a required item fails.

---

## 14. Out of Scope

Do not implement:

- final responsive CEO Workspace shell
- Sidebar removal
- full navigation redesign
- widget framework
- drag/drop dashboards
- user-customizable layouts
- Agent Harness
- unrestricted tool execution
- self-correction loop
- organizational memory
- analytics warehouse
- search platform
- notification center
- multi-user collaboration
- billing
- broad provider expansion
- cloud deployment work
- production caching infrastructure
- a second event transport when existing SSE can be extended
- generic workspace action dispatcher
- duplicated mutable read-model database without proven need

Record future requirements without implementing them.

---

## 15. Final Report

Return one evidence-based report with:

1. Starting/final/origin SHA and working-tree state
2. Sprint result and DoD count
3. Commits
4. Repository divergences
5. Public workspace schema
6. Projection service and authoritative sources
7. Next-action policy and precedence
8. Event cursor and reconnect semantics
9. Consistency and concurrency guarantees
10. API/auth/ownership behavior
11. Minimal dashboard proof
12. Performance/query review
13. Migration/bootstrap results
14. Verification matrix
15. Starting/ending tests and modified-test classification
16. Security/privacy audit
17. Existing-feature compatibility
18. Documentation updates
19. Scope control and Sprint 14 deferrals
20. Low-confidence areas
21. Sprint 14 handoff
22. Final state

Begin with Phase 0 and continue through Phase 5 without routine confirmation.
