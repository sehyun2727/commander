# Sprint 12 — PM ↔ CTO Planning and Project Specification

Execute this sprint autonomously from Phase 0 through Phase 5.

Expected baseline:
- local HEAD: aed4786
- origin/master: aed4786
- backend baseline: 248 passed / 4 skipped
- dashboard typecheck/build: PASS
- browser verification: previously UNVERIFIED

Repository and git state are authoritative. Verify every baseline claim before implementation.

Follow the current CLAUDE.md, architecture, decisions, UX specification, progress discipline, security rules, verification rules, and reporting format.

Do not stop for routine confirmation. Stop only for a hard blocker, destructive ambiguity, security/cost risk, or irreconcilable product decision.

---

## 1. Goal

Implement the first real PM ↔ CTO planning workflow.

At the end of Sprint 12:

1. The CEO submits a project request through the PM.
2. The PM analyzes the request and prepares structured product requirements.
3. The CTO analyzes technical feasibility, architecture, risks, and implementation approach.
4. PM and CTO exchange bounded, observable planning messages.
5. The system produces one versioned Project Specification.
6. The CEO can inspect the specification and either:
   - approve it,
   - request revision,
   - or reject/cancel planning.
7. Mission execution cannot start before specification approval.
8. Approved specifications can feed the existing PM → Engineer → Reviewer execution pipeline.
9. Mock mode performs the entire planning flow with zero provider API keys.
10. Existing Sprint 11 organization, hiring, and Employee configuration remain intact.

This sprint establishes deliberate planning before code execution. It does not redesign the CEO Workspace or implement a general autonomous-agent harness.

---

## 2. Product Model

The CEO communicates with the PM, not directly with the CTO.

The PM is the CEO-facing product owner.

The CTO is an internal leadership Employee responsible for:

- technical feasibility,
- architecture,
- implementation decomposition,
- dependency analysis,
- technical risk,
- non-functional requirements,
- verification strategy.

The system must make the collaboration observable without forcing the CEO to manage internal agents.

Expected flow:

CEO request
→ PM product analysis
→ PM asks CTO for technical review
→ CTO responds
→ PM revises or asks a bounded follow-up
→ Project Specification created
→ CEO review
→ approve / request revision / reject
→ approved specification enables execution

Planning must not silently become implementation.

---

## 3. Required Repository Inspection

Before changing code, inspect at minimum:

- CLAUDE.md
- PROGRESS.txt
- README.md
- docs/ARCHITECTURE.md
- docs/DECISIONS.md, especially Sprint 10–11 decisions
- docs/design/UX_SPEC.md
- git history from Sprint 10 through aed4786
- software-company template and CTO RoleSpec
- AgentORM/Employee configuration
- employee resolution and singleton enforcement
- model and skill-template registries
- current project, mission, task, workflow, decision, and event models
- WorkflowEngine
- AgentRuntime and PromptBuilder
- current PM/Engineer/Reviewer execution flow
- current mock provider behavior
- API auth/company ownership patterns
- dashboard mission creation, timeline, approval, and organization UX
- tests covering lifecycle, decisions, cancellation, errors, and mock E2E
- Alembic head and migration history

Determine whether the existing Project, Mission, Decision, Event, or task structures can be extended coherently. Do not introduce a duplicate aggregate without need.

---

## 4. Approved Product Decisions

### 4.1 CEO communicates through PM

The CEO submits the initial request and later reviews the final specification through the PM-facing workflow.

The CEO must not be required to directly message the CTO.

Internal PM ↔ CTO exchanges may be visible as an activity timeline, but the primary CEO UX should remain outcome-oriented.

### 4.2 CTO must be occupied

Planning that requires CTO review may start only if the company has an active Employee occupying the CTO Role.

If CTO is vacant:

- return a clear domain/API error,
- show a visible UI message,
- link or direct the CEO to hire a CTO,
- do not silently use another Role,
- do not auto-create a CTO Employee.

### 4.3 Planning is bounded

PM ↔ CTO discussion must have a deterministic upper bound.

Use a maximum of 6 internal planning turns total unless current architecture provides a better lower safe bound.

A turn is one persisted PM or CTO contribution.

The system must also stop when:

- agreement is reached,
- PM determines CEO clarification is required,
- CTO reports a blocking feasibility issue,
- the CEO cancels/rejects,
- an unrecoverable provider/runtime error occurs.

Do not create an unbounded autonomous conversation loop.

### 4.4 Missing information returns to the CEO

If the request lacks information that materially affects scope, architecture, security, cost, or acceptance criteria:

- planning enters a CEO-clarification-required state,
- PM presents concise structured questions,
- the CEO responds through the PM,
- planning resumes with a bounded continuation.

Do not let PM or CTO invent critical business requirements.

### 4.5 Project Specification is first-class, structured, and versioned

The Project Specification must be persisted as structured data, not only as transcript text.

At minimum it should represent:

- specification ID
- company/project ownership
- source mission/request
- version
- status
- title
- problem statement
- goals
- non-goals
- user-visible requirements
- acceptance criteria
- technical approach
- architecture/components
- data or migration impact
- security considerations
- observability requirements
- test/verification plan
- risks and mitigations
- dependencies
- assumptions
- unresolved questions
- implementation stages or task outline
- PM Employee ID
- CTO Employee ID
- timestamps
- approval/rejection metadata

Adapt exact fields to existing repository conventions. Avoid one giant unvalidated JSON blob when typed schemas or normalized ownership can provide safer boundaries.

### 4.6 Specification lifecycle

Use a clear state machine equivalent to:

- draft
- planning
- clarification_required
- ready_for_review
- approved
- revision_requested
- rejected
- cancelled
- failed

Use the smallest coherent set after inspecting current lifecycle patterns.

Every transition must be validated server-side.

Illegal transitions must return structured 4xx errors rather than 500.

### 4.7 Approval gates implementation

The existing execution pipeline must not begin code-changing stages before an associated specification is approved.

Approval must be authoritative on the server.

Frontend disabling alone is insufficient.

For backward compatibility, determine and document how legacy missions without specifications behave. Preferred behavior:

- existing historical/active missions remain valid,
- newly created code missions after Sprint 12 require an approved specification,
- non-code mission behavior remains unchanged unless architecture requires otherwise.

Do not retroactively break completed missions.

### 4.8 Revision preserves history

“Request revision” must not overwrite an approved or reviewable version in place.

Create a new version or revision lineage while preserving prior content, status, and audit history.

Only one current review candidate should exist for one planning request unless the architecture explicitly supports branches.

### 4.9 Planning is observable

Persist safe planning activity sufficient to explain:

- who spoke,
- which Employee was resolved,
- turn number,
- why another turn was needed,
- why planning stopped,
- why clarification was requested,
- how a specification version was created,
- approval/revision/rejection transitions.

Do not expose:

- provider secrets,
- hidden system prompts,
- unrestricted chain-of-thought,
- private credentials,
- raw internal reasoning.

Expose concise messages, summaries, decisions, structured rationale, and safe event metadata.

### 4.10 Employee-specific runtime configuration applies

PM and CTO planning must use the actual resolved Employees and their configured:

- model_ref
- skill_template_key
- allowed profile/capabilities

Do not use only RoleSpec defaults when an Employee-specific configuration exists.

Do not bypass the Sprint 10–11 Role → Employee resolver.

### 4.11 Mock mode is deterministic

Mock mode must generate deterministic:

- PM analysis,
- CTO review,
- clarification requests when triggered by fixture conditions,
- final specification,
- revision response,
- approval-ready output.

It must require zero API keys and be suitable for reliable tests.

### 4.12 Provider output is untrusted input

For real providers:

- request structured output where supported,
- validate every response,
- reject or safely retry malformed output with a strict limit,
- never directly persist unchecked provider JSON,
- never treat provider text as executable instructions,
- surface terminal failures visibly.

Retries must be bounded and observable.

---

## 5. Architecture Requirements

### 5.1 Keep orchestration separate from persistence and runtime

Do not enlarge WorkflowEngine into a monolith.

Prefer boundaries equivalent to:

- Planning orchestration/service
- Specification repository/service
- State-transition policy
- AgentRuntime/PromptBuilder
- Role → Employee resolver
- Event bus
- API routes

The planning orchestrator coordinates; it should not own all database, provider, prompt, and API concerns.

### 5.2 Avoid hardcoded Role behavior

PM and CTO are template Roles and Employee instances.

Do not scatter branches such as:

- if role == "cto"
- if role == "pm"
- fixed list indexing
- duplicated Role metadata

Use stage definitions, RoleSpec data, contracts, capabilities, and explicit planning-stage kinds.

A narrowly scoped CEO-counterpart exception may remain only if already justified by architecture decisions. Record any new exception.

Extend structural guards if needed so the new planning code cannot regress into Role literal branching.

### 5.3 Concurrency and idempotency

Review these races:

- duplicate planning start requests,
- simultaneous planning advancement,
- duplicate provider callbacks/retries,
- simultaneous approve and revision requests,
- two current specification versions,
- mission execution racing with approval.

Use database-backed uniqueness/versioning/locking where appropriate.

Required result:

- one authoritative active planning run per source request,
- no duplicate turn persistence,
- no double advancement,
- no simultaneous current review versions,
- no execution before committed approval,
- repeated safe requests are idempotent or clearly rejected.

### 5.4 Transactional consistency

Do not leave:

- a planning run advanced without its turn,
- a ready specification without persisted content,
- an approval event without approved state,
- a started execution without committed approval,
- partial revision lineage.

Emit success events only after durable state changes.

### 5.5 Ownership and authorization

Every endpoint must enforce company/project ownership through existing auth patterns.

The API must not trust company, Employee, mission, or specification IDs from the client without relationship validation.

### 5.6 Cancellation and failure cleanup

Cancellation or failure must:

- stop further planning advancement,
- preserve prior turns and specification drafts for audit,
- release any Employee runtime assignment if planning uses assignment state,
- avoid stranding PM or CTO as busy,
- prevent later stale callbacks from continuing the run,
- produce visible status and reason.

---

## 6. Required Backend Capabilities

Implement the smallest coherent API/service surface for:

1. Start planning from a CEO request or eligible mission.
2. Fetch planning-run state.
3. List safe planning turns/activity.
4. Submit CEO clarification answers.
5. Fetch current Project Specification.
6. Fetch specification version history.
7. Approve specification.
8. Request revision with CEO feedback.
9. Reject or cancel planning.
10. Resume or advance planning where current architecture requires an explicit trigger.
11. Begin existing execution only when approval conditions are met.

Prefer resource-oriented company/project-scoped endpoints following current naming conventions.

Avoid a single generic action endpoint if typed endpoints better represent state transitions.

All mutations require visible structured errors.

---

## 7. Required Dashboard UX

Extend existing project/mission UX rather than implementing the future CEO Workspace redesign.

Required behavior:

### Planning start

- CEO enters the project request through the existing PM-facing flow.
- UI explains that PM and CTO will prepare a specification before implementation.
- If CTO is vacant, show a clear hiring requirement and path to Employees/Organization.

### Planning status

Show a clear status such as:

- PM analyzing
- CTO reviewing
- Waiting for CEO clarification
- Revising
- Ready for approval
- Approved
- Rejected
- Cancelled
- Failed

Do not display an indefinite generic spinner.

### Internal collaboration

Show an understandable activity timeline containing safe summaries:

- PM requirement summary
- CTO feasibility/architecture review
- questions or disagreement
- resolution reason
- specification version created

Do not expose hidden chain-of-thought.

### Clarification

When clarification is required:

- show concise PM-authored questions,
- accept CEO answers,
- prevent empty submissions,
- preserve previous questions and answers,
- resume planning visibly.

### Specification review

Display structured sections, not only raw JSON or one markdown block.

At minimum show:

- goals/non-goals
- requirements
- acceptance criteria
- technical approach
- risks
- test plan
- unresolved questions
- version and status

### CEO actions

At ready_for_review:

- Approve
- Request revision
- Reject or cancel

Revision feedback is required.

Prevent duplicate submissions and show success/error feedback.

### Approved state

Show that implementation is now enabled.

Provide the existing next execution action or automatically continue only if current product semantics clearly support it.

Do not silently start code execution merely because the review page rendered.

### Accessibility and responsiveness

Preserve:

- labels
- keyboard access
- focus handling
- loading and disabled states
- mobile/basic responsive behavior
- current visual patterns

All mutations must use the existing global toast/error system.

---

## 8. Phases

## Phase 0 — Baseline and Design Audit

1. Verify HEAD, origin/master, and working-tree state.
2. Identify and preserve the reported unrelated Sprint 10 rename if still present; do not silently include or delete it.
3. Run baseline tests, dashboard typecheck, and build.
4. Verify Sprint 11 migration state and fresh database behavior.
5. Inspect current lifecycle, decision, event, runtime, resolver, and UI architecture.
6. Verify CTO vacancy/hiring behavior.
7. Determine the exact legacy-mission compatibility policy.
8. Determine the specification schema and state machine.
9. Determine planning turn semantics and the bounded-loop rule.
10. Audit real-provider structured-output support and mock-provider extension points.
11. Replace PROGRESS.txt with a live Sprint 12 checklist.
12. Record material design decisions before implementation.
13. Commit/push the Phase 0 checkpoint if consistent with repository practice.

## Phase 1 — Planning and Specification Domain

1. Add persistence models for planning runs, turns, specifications, and version lineage as required.
2. Add explicit status enums and legal transition rules.
3. Add ownership, current-version, and idempotency constraints.
4. Add Alembic migration and safe compatibility behavior.
5. Implement typed domain schemas.
6. Implement specification creation and revision semantics.
7. Implement transition validation.
8. Implement cancellation/failure cleanup rules.
9. Add domain tests for legal and illegal transitions.
10. Add migration upgrade and fresh database tests.
11. Add concurrency tests for duplicate start/current version/approval races.
12. Update PROGRESS.txt.
13. Commit/push Phase 1.

## Phase 2 — PM ↔ CTO Planning Orchestration

1. Implement the planning orchestrator outside WorkflowEngine.
2. Resolve actual PM and CTO Employees through the central resolver.
3. Use Employee-specific model and skill configuration.
4. Add data-driven planning stage definitions.
5. Build PM and CTO prompt/context contracts.
6. Implement structured provider-response validation.
7. Implement bounded retries for malformed provider output.
8. Implement the maximum-turn and stop-condition policy.
9. Implement clarification-required flow.
10. Implement deterministic mock planning behavior.
11. Persist safe turns, summaries, reasons, and events.
12. Ensure cancellation/failure releases runtime assignments if used.
13. Add tests for:
    - successful PM→CTO planning
    - missing CTO
    - clarification path
    - blocking feasibility issue
    - turn limit
    - malformed provider output
    - bounded retry
    - cancellation
    - runtime cleanup
    - deterministic mock result
    - Employee configuration usage
14. Update structural hardcoding guards if needed.
15. Update PROGRESS.txt.
16. Commit/push Phase 2.

## Phase 3 — API, Approval Gate, and Existing Pipeline Integration

1. Add company/project-scoped planning and specification endpoints.
2. Enforce auth and ownership.
3. Expose safe public schemas.
4. Implement approval, revision, rejection, cancellation, and clarification mutations.
5. Make mutations idempotent or reject duplicates predictably.
6. Enforce approved-specification gate server-side for new code missions.
7. Preserve the documented legacy-mission policy.
8. Convert approved specification stages into inputs for the existing execution pipeline without bypassing WorkflowEngine.
9. Ensure no execution starts before durable approval.
10. Add API/integration tests for all endpoints and conflicts.
11. Run a mock API flow:
    - create company/project
    - verify CTO vacancy failure or hire CTO
    - submit CEO request
    - PM analysis
    - CTO review
    - clarification when fixture requests it
    - CEO answer
    - ready specification
    - request revision
    - new version
    - approve
    - begin existing PM→Engineer→Reviewer execution
    - complete mission
12. Verify events and status transitions.
13. Update PROGRESS.txt.
14. Commit/push Phase 3.

## Phase 4 — Dashboard Planning and Specification UX

1. Add planning start UX to the existing project/mission flow.
2. Show CTO-vacancy guidance.
3. Add status-specific planning view.
4. Add safe PM↔CTO activity timeline.
5. Add clarification question/answer UI.
6. Add structured specification review.
7. Add version history and current-version indication.
8. Add approve/revision/reject/cancel actions.
9. Require revision feedback.
10. Prevent duplicate submissions.
11. Wire all errors to global error visibility.
12. Refetch/invalidate correct queries after transitions.
13. Show approved execution readiness.
14. Preserve loading, empty, failure, and cancellation states.
15. Run dashboard typecheck and production build.
16. Perform browser verification if tooling exists.
17. If unavailable, explicitly mark browser behavior UNVERIFIED.
18. Update PROGRESS.txt.
19. Commit/push Phase 4.

## Phase 5 — Full Verification and Documentation

1. Run full backend tests.
2. Run dashboard typecheck.
3. Run dashboard production build.
4. Verify migration from Sprint 11 revision.
5. Verify fresh database bootstrap.
6. Run mock E2E with zero provider keys.
7. Verify both direct-ready and clarification/revision flows.
8. Verify execution cannot start before approval.
9. Verify existing historical/active mission compatibility.
10. Verify approval/execution concurrency behavior.
11. Audit auth and company ownership.
12. Audit provider output validation and retry bounds.
13. Audit event/API payloads for secrets and hidden reasoning.
14. Audit Role hardcoding.
15. Audit WorkflowEngine growth and module boundaries.
16. Audit cancellation/failure cleanup.
17. Audit all dashboard mutations for visible errors.
18. Inspect the complete diff for scope leakage.
19. Update:
    - CLAUDE.md
    - PROGRESS.txt
    - README.md when user workflow changed
    - docs/ARCHITECTURE.md
    - docs/DECISIONS.md
    - docs/design/UX_SPEC.md
20. Record Sprint 13+ deferrals.
21. Commit/push final documentation.
22. Confirm clean intended working tree and local HEAD == origin/master.
23. Do not alter the unrelated pre-existing rename unless explicitly necessary and justified.

---

## 9. Sprint-Specific Tests

Tests must prove behavior, not just object counts.

Required coverage:

- CTO vacancy blocks planning
- valid CTO enables planning
- PM and CTO Employees are centrally resolved
- Employee-specific model/skill settings are used
- one active planning run per source request
- duplicate start safety
- deterministic turn ordering
- bounded turn count
- agreement stop
- clarification stop and resume
- blocking feasibility stop
- malformed provider response validation
- bounded retry and terminal failure
- deterministic mock planning
- specification field validation
- specification version history
- revision does not overwrite prior version
- approval/revision race
- duplicate approval behavior
- rejection/cancellation
- failure cleanup
- authorization and cross-company isolation
- safe public schemas
- no provider secrets or hidden reasoning
- execution blocked before approval
- execution enabled after approval
- existing mock PM→Engineer→Reviewer lifecycle remains functional
- migration from Sprint 11
- fresh database

When changing existing tests, report why each change was necessary and do not weaken assertions merely to pass.

---

## 10. Definition of Done

Sprint 12 is complete only when:

1. Baseline and remote state are verified.
2. Planning run and specification are first-class persisted domain data.
3. Specification lifecycle is enforced server-side.
4. Specification versions preserve history.
5. PM and CTO are resolved through the central resolver.
6. Actual Employee runtime configuration is used.
7. CTO vacancy fails clearly without fallback.
8. PM ↔ CTO planning is bounded and deterministic in mock mode.
9. Missing material information returns structured questions to the CEO.
10. CEO answers can resume planning.
11. Provider output is validated before persistence.
12. Retries are bounded and observable.
13. Planning activity is observable without exposing hidden reasoning.
14. Duplicate start/advance requests do not duplicate work.
15. Concurrent approval/revision cannot corrupt state.
16. Failed/cancelled planning does not strand Employees.
17. Project Specification contains product, technical, risk, and verification sections.
18. CEO can inspect the specification.
19. CEO can approve it.
20. CEO can request revision with feedback.
21. CEO can reject or cancel.
22. Revision creates preserved version history.
23. New code execution is blocked before approval.
24. Approved specification can enter the existing execution pipeline.
25. Existing legacy behavior follows a documented compatibility policy.
26. Existing Sprint 11 hiring/configuration remains functional.
27. All endpoints enforce auth and ownership.
28. All mutation failures are visible.
29. Mock E2E succeeds with zero API keys.
30. Full backend test suite passes.
31. Dashboard typecheck passes.
32. Dashboard production build passes.
33. Sprint 11→12 migration passes.
34. Fresh database bootstrap passes.
35. Browser verification is accurately reported.
36. No role-specific ORM type or scattered Role branches are introduced.
37. WorkflowEngine does not become a planning monolith.
38. No secrets, chain-of-thought, or executable provider output is exposed.
39. Documentation matches implementation.
40. Final state is pushed and local HEAD equals origin/master.

Do not claim complete if any required item fails. Mark unsupported verification honestly as UNVERIFIED.

---

## 11. Out of Scope

Do not implement:

- Sprint 13 CEO Workspace backend redesign
- Sprint 14 responsive workspace shell
- Sprint 15 widget system
- Sprint 16 Agent Harness
- unrestricted tool execution
- free shell
- autonomous repository-editing loop outside the existing execution pipeline
- Sprint 17 self-correction
- Sprint 18 memory/learning
- direct CEO↔CTO chat product
- unbounded multi-agent group chat
- parallel team execution
- Designer/QA/DevOps/Security full employee workflows
- arbitrary user-created Roles
- arbitrary skill/tool authoring
- general document collaboration
- marketplace
- multi-user collaboration
- cloud deployment work
- broad provider expansion
- billing or usage metering

Record future needs without implementing them.

---

## 12. Final Report

Return one evidence-based report containing:

1. Starting/final/origin SHA and working-tree state
2. Sprint result and completed DoD count
3. Commits
4. Repository divergences from this brief
5. Planning domain and state machine
6. Specification schema and versioning
7. PM ↔ CTO orchestration and turn bound
8. Employee resolution and runtime configuration usage
9. Clarification, revision, approval, rejection, and cancellation behavior
10. Concurrency/idempotency guarantees
11. API and ownership enforcement
12. Dashboard UX
13. Existing execution-pipeline integration
14. Migration results
15. Verification matrix:
    - unit/domain
    - API
    - integration
    - concurrency
    - migration
    - typecheck
    - build
    - browser
    - mock E2E
    - real LLM E2E
16. Starting/ending test counts and modified-test classification
17. Security and observability audit
18. Documentation updates
19. Scope control and Sprint 13+ deferrals
20. Low-confidence areas
21. Sprint 13 handoff
22. Final state

Begin with Phase 0 and continue without routine confirmation.
