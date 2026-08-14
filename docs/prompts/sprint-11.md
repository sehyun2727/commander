# Sprint 11 — Build the Company: CTO, Hiring, and Employee Configuration

You are implementing Commander Sprint 11 as one autonomous sprint.

Base commit:
- Expected local HEAD: 29fd400
- Expected origin/master: 29fd400

Do not trust this prompt alone. Verify the repository before implementation.

Execution rules:
- Do not stop for routine confirmation.
- Read the repository and its current documents before deciding.
- Inspect first, reason, decide, record non-obvious decisions, and continue.
- Make reasonable engineering decisions within this sprint’s boundaries.
- Do not silently widen scope.
- Keep PROGRESS.txt current throughout execution.
- Commit and push at meaningful phase checkpoints.
- Run all required verification.
- Never report a verification level that was not actually performed.
- If browser automation is unavailable, say so explicitly and mark browser behavior UNVERIFIED.
- Finish all phases, push the final state, and return one complete final report.

---

## 0. Sprint Objective

Transform Commander’s role/employee architecture into an organization the CEO can actually configure.

At the end of Sprint 11:

1. The software-company template includes a first-class CTO RoleSpec.
2. A company can hire and manage multiple Employees for eligible roles.
3. Singleton leadership roles remain protected.
4. The CEO can choose a Role and configure an Employee’s model and skill template during hiring.
5. The existing deterministic Role → Employee resolver uses those hired Employees.
6. The organization UI clearly distinguishes:
   - Role = template-owned position
   - Employee = company-owned runtime instance
7. Existing PM → Engineer → Reviewer mission execution remains compatible.
8. Mock mode continues to work without provider credentials.

This sprint creates the organization that Sprint 12 will use. It does not implement PM↔CTO planning.

---

## 1. Product Context

Sprint 10 made Role and Employee separate concepts, but the organization is still mostly template-seeded and static.

The CEO needs to be able to:

- see which positions exist,
- understand which positions are leadership or workers,
- hire an Employee into a Role,
- hire multiple Employees into non-singleton Roles,
- configure the Employee without editing template data,
- see why hiring failed,
- see the resulting Employee in the company organization.

The CEO is building a company, not manipulating database records.

Use CEO-facing language such as:

- Hire employee
- Position / Role
- Employee name
- Model
- Skill template
- Leadership position already filled

Avoid exposing internal implementation terminology unless necessary.

---

## 2. Architectural Context

Sprint 10 established these boundaries:

- RoleSpec is immutable template-owned data.
- Employee/AgentORM is a company-owned runtime instance.
- Employee identity is linked through role_key.
- Role → Employee resolution is deterministic.
- singleton Roles are enforced in the employee service.
- role-specific behavior must be derived from data rather than scattered hardcoded branches.
- the Roles API is read-only and intentionally exposes safe metadata only.

Sprint 11 must build on those boundaries rather than bypass them.

The central invariant is:

Role defines what a position is.
Employee defines who occupies it and how that Employee is configured.

Do not mutate RoleSpec to represent a hired person.

---

## 3. Required Repository Reading

Before changing code, inspect at minimum:

- CLAUDE.md
- PROGRESS.txt
- README.md
- docs/ARCHITECTURE.md
- docs/DECISIONS.md, especially Sprint 10 decisions #163 onward
- docs/design/UX_SPEC.md
- app/templates/software_company.py
- app/modules/workflow_engine/employee_resolution.py
- current employee/agent ORM, schemas, services, and routes
- current project/company creation and founding-profile code
- current model registry/provider abstraction
- current API router registration
- apps/dashboard employee and role UI
- relevant hooks and API clients
- migrations
- tests added or changed in Sprint 10
- recent git history from 29fd400 backward through Sprint 10

Search before deciding names and locations. Follow existing module boundaries and conventions.

---

## 4. Approved Decisions

Treat the following as approved unless the actual repository proves them impossible.

### 4.1 CTO is a first-class RoleSpec

Add CTO to the software-company template.

Expected semantics:

- key: "cto"
- category: "leadership"
- singleton: true
- clear third-person description
- appropriate title, contract, permissions, and model reference
- immutable template-owned data

Do not create a CTO-specific ORM type.

Do not implement CTO planning or discussion behavior in this sprint.

### 4.2 Singleton policy

At minimum, existing singleton leadership Roles and CTO must reject a second active Employee for the same company and role_key.

Non-singleton worker Roles must support multiple Employees.

The singleton guarantee must cover every reachable write path, not only the new UI.

### 4.3 Hiring is a company-owned mutation

Hiring creates an Employee instance associated with:

- company/project
- role_key
- employee display name or canonical name
- selected model reference
- selected skill template, if applicable
- valid initial runtime state
- required timestamps and metadata

Use the repository’s actual ownership vocabulary consistently. Do not introduce a parallel organization aggregate if the current Project/Company model already owns Employees.

### 4.4 Employee configuration is not Role configuration

The RoleSpec default model/profile may provide defaults, but the hired Employee owns its selected runtime configuration.

Changing an Employee’s model or skill template must not mutate the RoleSpec or affect other Employees.

### 4.5 Selection data comes from canonical registries

Role options must come from the template’s RoleSpecs.

Model options must come from the existing model registry/provider abstraction.

Skill-template options must come from one canonical allowlisted registry or typed definition.

Do not duplicate lists in API routes and frontend components.

### 4.6 Skills are not arbitrary tools

“Skill template selection” means selecting a safe, predefined capability/profile template.

It must not:

- grant free shell access,
- accept arbitrary executable text,
- accept arbitrary tool names from the client,
- expand the Employee beyond server-side allowlists,
- bypass Role permissions or future Harness security boundaries.

If no real skill-template registry exists, create the smallest canonical, typed, server-owned registry required for Sprint 11. Do not build the Sprint 16 Agent Harness.

### 4.7 Existing resolver remains central

Mission assignment/execution must continue to resolve role_key to an Employee through the Sprint 10 resolver.

Do not introduce an independent “selected employee” branch that bypasses deterministic resolution unless the repository already has an approved explicit-assignment mechanism.

### 4.8 API is authoritative

The server validates:

- company ownership,
- role existence,
- singleton eligibility,
- model reference,
- skill-template key,
- employee name constraints,
- legal state transitions.

Frontend filtering is convenience only, not enforcement.

### 4.9 Observable failures

Every hiring or employee-configuration failure must produce:

- a structured API error,
- a visible UI error through the existing toast/error system,
- no partial Employee row,
- no silent fallback to an unrelated Role/model/skill.

### 4.10 Concurrency must be reviewed now

Sprint 10 intentionally deferred the singleton TOCTOU risk because no hiring route existed.

Sprint 11 creates a reachable mutation path, so concurrent singleton hiring must now be reviewed and resolved.

Do not claim that a service-level check-then-insert alone is race-safe.

Select a design compatible with the repository’s supported databases and test environment. Prefer a database-backed invariant where feasible. If cross-database limitations require a different transaction/locking strategy, document the exact guarantee and residual risk in DECISIONS.md.

---

## 5. Current State to Verify

Confirm these claims against the actual code before implementation:

- Sprint 10 HEAD is 29fd400.
- RoleSpec is the canonical role source.
- CTO does not yet exist.
- create_employee() exists but is not exposed through a hiring route.
- leadership singleton checks currently live in the service layer.
- the resolver supports multiple Employees deterministically.
- Roles API exposes safe metadata.
- Employees UI groups Role and Employee information.
- model registry exists and is separate from role labels.
- no canonical skill-template registry may exist yet.
- baseline tests are 218 passed / 4 skipped.
- dashboard typecheck/build are green.
- API-level mock E2E is green.
- browser verification for Sprint 10 was not performed.

If any claim is wrong, update PROGRESS.txt and adapt implementation without widening the sprint. Record material divergence in DECISIONS.md.

---

## 6. Target State

### 6.1 Template

The software-company template contains CTO as a valid leadership RoleSpec.

Adding CTO must not require hardcoded engine or prompt-builder branches.

The Sprint 10 AST role-hardcoding guard must remain green and should be expanded only if Sprint 11 introduces a new production surface that should be protected.

### 6.2 Employee persistence

Persist the Employee’s selected runtime configuration using the existing AgentORM/Employee model or the smallest coherent extension to it.

At minimum represent:

- role_key
- employee name
- model_ref
- skill_template_key, nullable only when the design defines a safe default
- assignment/runtime state already required by the system

Avoid storing a mutable copy of the complete RoleSpec.

If schema changes are needed:

- create an Alembic migration,
- define defaults/backfill for existing rows,
- preserve existing companies and seeded Employees,
- verify upgrade from the previous revision,
- verify a fresh database.

### 6.3 Canonical skill templates

Provide a small, canonical set of skill templates sufficient to prove the architecture.

The exact names should be chosen after inspecting current profile/tool concepts. Keep the set minimal.

Each template should have typed, immutable metadata such as:

- key
- title
- description
- allowed capability identifiers or profile metadata

Do not execute new tools in this sprint merely because a template references them.

Expose only safe presentation fields to the client.

### 6.4 Hiring service

Implement or extend one authoritative employee service with behavior equivalent to:

- list eligible Roles,
- validate role_key,
- validate model_ref,
- validate skill_template_key,
- enforce singleton policy atomically,
- create Employee,
- assign safe initial state,
- return a public Employee representation,
- emit an observable hiring event.

Do not duplicate business rules in the route.

Define a specific domain exception for singleton conflicts and map it to an appropriate API status, preferably 409 Conflict.

Validation failures should normally be 4xx, not 500.

### 6.5 Employee update

Allow the CEO to update mutable Employee configuration required by this sprint:

- display/canonical name, if the existing naming model permits it
- model_ref
- skill_template_key

Do not allow changing:

- company ownership,
- immutable Employee ID,
- role_key through a generic update endpoint,
- runtime assignment fields through this API.

If changing Role is needed later, defer it as an explicit transfer/reassignment flow.

Do not allow destructive actions that would strand an active mission.

Firing/deleting Employees is not required unless the current architecture already supports it safely. Do not add it casually.

### 6.6 API

Add coherent company/project-scoped endpoints following existing route conventions.

Required capabilities:

- list available Role metadata for hiring
- list allowed model options
- list allowed skill-template options
- create/hire Employee
- update allowed Employee configuration
- list Employees with role and configuration metadata required by the UI

Prefer extending existing endpoints over creating duplicate representations.

Keep Role API read-only.

Never expose:

- provider secrets,
- API keys,
- internal prompts,
- unrestricted tool definitions,
- executable configuration.

### 6.7 Events and observability

Add event types only where they represent real domain events.

At minimum, successful hiring should be observable with safe payload data, for example:

- company/project ID
- employee ID
- role_key
- model_ref
- skill_template_key

Do not include credentials or full prompt/profile contents.

Failures must remain visible through logs/API/UI. Do not emit a success event before the transaction succeeds.

### 6.8 Dashboard UX

Extend the existing Employees/Organization experience rather than redesigning the full application.

Required UX:

1. A clear “Hire employee” action.
2. A form or dialog with:
   - Role
   - Employee name
   - Model
   - Skill template
3. Defaults derived from RoleSpec/registry data where appropriate.
4. Singleton Roles visibly marked.
5. Filled singleton Roles disabled or rejected clearly.
6. Multiple Employees visible under non-singleton Roles.
7. Each Employee shows at least:
   - name
   - Role title
   - model
   - skill template
   - runtime status
8. An edit/configure action for mutable Employee settings.
9. Loading, empty, success, and error states.
10. Existing toast/error surfacing wired for all mutations.

The UI must not hardcode the available Roles, models, or skill templates.

Do not implement the Sprint 13–15 CEO Workspace redesign or widget system.

### 6.9 Founding behavior and compatibility

New companies should receive a coherent founding organization after CTO is added.

Inspect current seeding behavior and decide whether CTO is:

- automatically seeded as a founding leadership Employee, or
- an initially vacant Role hired by the CEO.

Preferred product behavior for Sprint 11:
- keep existing PM/Engineer/Reviewer founding behavior compatible,
- make CTO visibly available for the CEO to hire rather than silently auto-hiring it,
- unless repository invariants make that unsafe.

Record the final choice and rationale in DECISIONS.md.

Existing companies must not break because CTO was added to template data.

No migration should fabricate a CTO Employee for every existing company unless explicitly justified.

---

## 7. Non-negotiable Constraints

1. Role remains template-owned immutable data.
2. Employee remains company-owned runtime data.
3. No role-specific ORM subclasses.
4. No duplicated canonical role/model/skill option lists.
5. No arbitrary tool or executable skill input.
6. No free shell.
7. No provider secrets exposed to frontend or events.
8. Mock mode must require zero provider API keys.
9. Existing provider abstraction must remain intact.
10. Existing deterministic resolver remains the assignment authority.
11. No silent mutation failure.
12. No partial Employee after failed hiring.
13. Singleton enforcement must account for concurrent requests.
14. Do not enlarge WorkflowEngine into a hiring/configuration service.
15. Do not modify tests merely to accommodate implementation details unless justified.
16. Do not chase a test-count KPI.
17. Do not claim browser verification if only API or build verification occurred.
18. Update documentation with the implementation.
19. Use the existing auth/company-access boundaries on every new endpoint.
20. Preserve backward compatibility for existing seeded Employees and missions.

---

## 8. Phases

## Phase 0 — Baseline and Sprint State

1. Verify local HEAD and origin/master.
2. Confirm working tree state.
3. Read required repository documents and core code.
4. Run the baseline backend test suite.
5. Run dashboard typecheck and build.
6. Inspect the current Alembic head and database revision workflow.
7. Verify current mock mission E2E at least at API level if the environment supports it.
8. Audit Sprint 10’s browser-UNVERIFIED items relevant to Sprint 11.
9. Replace PROGRESS.txt with a Sprint 11 live checklist containing every phase item and DoD item.
10. Commit/push the Sprint 11 baseline/progress checkpoint if repository convention supports it.

Do not change product behavior in Phase 0 except fixing a genuine blocker that prevents Sprint 11 work. Record any blocker fix separately.

## Phase 1 — CTO and Canonical Configuration Data

1. Add CTO RoleSpec.
2. Define CTO title/category/singleton/description/contract/permissions/model default.
3. Verify RoleSpec immutability.
4. Confirm CTO appears automatically in role-derived APIs/UI without hardcoded branches.
5. Add or formalize a canonical typed skill-template registry.
6. Ensure skill metadata is immutable and server-owned.
7. Ensure model choices come from the current model registry.
8. Add safe read APIs/schemas for model and skill choices if no suitable API exists.
9. Add tests for:
   - CTO metadata
   - singleton classification
   - RoleSpec canonicality
   - skill-template immutability
   - safe registry serialization
   - no duplicated role/model/skill source
10. Run targeted and full relevant tests.
11. Update PROGRESS.txt immediately.
12. Commit/push Phase 1.

## Phase 2 — Persistence and Atomic Hiring Domain

1. Determine the smallest coherent schema change for per-Employee model/skill configuration.
2. Add migration if required.
3. Backfill existing Employee rows safely.
4. Preserve existing role_key and runtime state semantics.
5. Implement authoritative hire_employee/create_employee behavior.
6. Implement atomic singleton protection.
7. Validate Role, model, skill, ownership, and name.
8. Define domain errors and status mapping.
9. Emit a hiring event after successful persistence.
10. Implement allowed Employee configuration updates.
11. Reject role transfer through generic update.
12. Protect active/busy Employee invariants.
13. Add tests for:
    - successful CTO hire
    - second CTO conflict
    - second PM/Reviewer conflict
    - multiple Engineer hires
    - invalid role/model/skill
    - cross-company access
    - rollback/no partial row
    - concurrent singleton creation
    - independent Employee configuration
    - existing-row migration/backfill
    - fresh database migration
14. Run migration and domain tests.
15. Update PROGRESS.txt immediately.
16. Record concurrency/schema decisions.
17. Commit/push Phase 2.

## Phase 3 — API and Runtime Integration

1. Add or extend company/project-scoped employee endpoints.
2. Reuse the authoritative service.
3. Apply existing authentication and company access checks.
4. Return stable public schemas.
5. Keep Role endpoints read-only.
6. Expose safe role/model/skill option metadata.
7. Ensure every new mutation returns structured errors.
8. Confirm Employee listing includes configuration needed by the UI.
9. Confirm hired Employees participate in the existing resolver.
10. Verify deterministic selection with multiple hired Engineers.
11. Verify singleton leadership Roles resolve correctly.
12. Verify no route bypasses singleton or registry validation.
13. Add API/integration tests.
14. Run an API-level flow:
    - create company/project
    - inspect Roles
    - hire CTO
    - reject second CTO
    - hire at least two Engineers
    - edit one Engineer’s model/skill
    - list Employees and verify independence
    - execute a mock mission
    - observe deterministic Employee resolution and events
15. Update PROGRESS.txt immediately.
16. Commit/push Phase 3.

## Phase 4 — Dashboard Hiring and Configuration UX

1. Extend current Employees/Organization page.
2. Add “Hire employee”.
3. Build Role/model/skill selection from API data.
4. Add Employee name input and validation.
5. Show singleton and occupied states.
6. Support multiple Employees under worker Roles.
7. Add Employee configuration editing.
8. Wire loading, success, empty, and error states.
9. Connect mutation errors to the global toast/error system.
10. Invalidate/refetch the correct queries after mutation.
11. Prevent duplicate submission.
12. Preserve accessible labels, keyboard behavior, and focus handling.
13. Do not hardcode role/model/skill option arrays.
14. Run typecheck.
15. Run production build.
16. If browser tooling exists, verify:
    - hire CTO
    - second CTO visible failure
    - hire two Engineers
    - edit one Employee independently
    - refresh persistence
    - responsive layout
    - keyboard/form behavior
17. If browser tooling does not exist, explicitly record browser verification as UNVERIFIED; do not substitute build/typecheck and call it browser verification.
18. Update PROGRESS.txt immediately.
19. Commit/push Phase 4.

## Phase 5 — Regression, Security, Documentation, Close-out

1. Run the full backend test suite.
2. Run dashboard typecheck.
3. Run dashboard production build.
4. Run mock E2E with zero provider keys.
5. Re-run hiring API integration flow.
6. Verify migration from the previous Sprint 10 database revision.
7. Verify fresh database bootstrap.
8. Review git diff for unexpected changes and scope leakage.
9. Audit new routes for auth and company ownership.
10. Audit API/event output for secrets and unsafe skill details.
11. Audit role/model/skill hardcoding.
12. Audit WorkflowEngine for unrelated growth.
13. Audit all mutation hooks for visible error handling.
14. Classify verification separately:
    - unit
    - API
    - integration
    - migration
    - typecheck
    - build
    - browser
    - mock E2E
    - real LLM E2E
15. Update:
    - CLAUDE.md
    - PROGRESS.txt
    - docs/ARCHITECTURE.md
    - docs/DECISIONS.md
    - docs/design/UX_SPEC.md
    - README.md only if startup/user workflow changed
16. Record deliberate Sprint 12 deferrals.
17. Mark PROGRESS.txt complete only after all verification and documentation are complete.
18. Commit/push final documentation and progress state.
19. Confirm local HEAD equals origin/master.

---

## 9. Out of Scope

Do not implement:

- PM↔CTO planning conversations
- Project Specification
- Requirement Discovery
- CEO clarification/approval workflow
- CTO “discuss” stage
- Sprint 13 CEO Workspace backend
- Sprint 14 UI shell redesign
- Sprint 15 widgets
- Sprint 16 Agent Harness
- iterative repository-aware tool loop
- Sprint 17 self-correction
- Sprint 18 memory/learning
- employee firing unless already safely supported
- arbitrary Role creation by users
- Role editing
- arbitrary skill/tool authoring
- free shell
- second company template
- multi-user collaboration
- marketplace
- parallel frontend/backend execution
- full Designer/QA/DevOps/Security employee implementations
- broad provider expansion
- cloud deployment work

If a future requirement is discovered, record it in DECISIONS.md and continue without implementing it.

---

## 10. Definition of Done

Sprint 11 is complete only when all applicable items are satisfied.

1. Local and remote HEAD are equal.
2. CTO exists as a first-class immutable singleton RoleSpec.
3. CTO appears through data-driven Role APIs/UI without engine-specific hardcoding.
4. Canonical, typed, immutable skill-template metadata exists.
5. Model options come from the canonical model registry.
6. Employee runtime configuration persists independently per Employee.
7. Existing Employee rows migrate/backfill safely.
8. Company can hire a CTO.
9. A second CTO is rejected with a visible 4xx conflict.
10. Existing singleton leadership roles remain protected.
11. Company can hire multiple Employees into a non-singleton worker Role.
12. Concurrent singleton hiring cannot produce two singleton Employees.
13. Invalid Role/model/skill input is rejected server-side.
14. Failed hiring leaves no partial Employee.
15. Employee mutable configuration can be updated without changing RoleSpec or other Employees.
16. Generic update cannot silently transfer an Employee to another Role/company.
17. New endpoints enforce auth and company ownership.
18. Hiring emits a safe observable event after success.
19. Hired Employees are used by the deterministic resolver.
20. Existing PM→Engineer→Reviewer execution remains functional.
21. Mock E2E works with zero API keys.
22. Dashboard provides hiring and configuration UX.
23. UI options are API/data-driven rather than duplicated constants.
24. All mutation failures are visible.
25. Backend full test suite passes.
26. Dashboard typecheck passes.
27. Dashboard production build passes.
28. Migration upgrade from Sprint 10 succeeds.
29. Fresh database bootstrap succeeds.
30. Browser verification is either actually completed or explicitly UNVERIFIED.
31. No secrets or executable skill definitions are exposed.
32. Role-hardcoding guard remains green.
33. No Sprint 12+ functionality leaked into this sprint.
34. Architecture and UX documents match the implementation.
35. PROGRESS.txt reflects actual completion, not reported completion.
36. Final commit is pushed and origin/master matches local HEAD.

Do not define success by test count. Report the actual count, but quality and behavioral coverage matter more.

---

## 11. Verification Matrix

Report each independently:

### Backend unit/domain tests
Required.

### API tests
Required.

### Integration tests
Required for hiring, update, singleton conflict, ownership, and resolver participation.

### Concurrency test
Required for singleton hiring.

A purely sequential test does not prove concurrency safety.

### Migration verification
Required:
- upgrade from prior revision
- fresh database

### Dashboard typecheck
Required.

### Dashboard production build
Required.

### Browser verification
Required when tooling is available.

If unavailable:
- prove that tooling is unavailable,
- mark browser interaction UNVERIFIED,
- do not call API verification browser verification.

### Mock E2E
Required with zero provider keys.

Must cover:
- hiring
- multiple Employees
- resolver use
- existing mission lifecycle

### Real LLM E2E
Not required for Sprint 11 unless credentials and environment are explicitly available.
Report UNVERIFIED otherwise.

---

## 12. Testing Discipline

When modifying existing tests, classify every change in the final report:

1. behavior intentionally changed,
2. implementation-detail coupling only,
3. incorrect or obsolete prior expectation,
4. regression coverage added without changing existing assertions.

Do not weaken assertions merely to make the suite green.

Add self-tests for structural guards if a new guard is introduced.

Prefer behavioral tests over tests that only count objects or inspect source substrings.

---

## 13. Documentation Requirements

Update documentation to reflect actual implementation.

### CLAUDE.md

Document:

- Sprint 11 organization model
- CTO Role
- hiring/configuration boundaries
- canonical registries
- singleton concurrency guarantee
- autonomous sprint workflow if necessary

### docs/ARCHITECTURE.md

Document:

- Role → Employee → runtime configuration relationship
- hiring service boundary
- model and skill-template registries
- API ownership and validation
- event flow
- singleton enforcement mechanism
- resolver integration

### docs/DECISIONS.md

Record only non-obvious decisions, including:

- CTO founding behavior
- persistence design
- singleton concurrency strategy
- skill-template representation/security
- mutable versus immutable Employee fields
- any deliberate deferral

Continue existing decision numbering.

### docs/design/UX_SPEC.md

Document:

- hiring entry point
- form fields and defaults
- singleton occupied state
- multiple Employee display
- editing flow
- loading/error/success behavior
- browser verification status

### PROGRESS.txt

Use as a live state board.

For every completed item:

- check it immediately,
- update “Now working on,”
- update count and percentage.

Do not change 0% to 100% only at sprint end.

---

## 14. Commit and Push Discipline

Use meaningful phase checkpoint commits, not dozens of trivial commits.

Suggested shape; adapt scopes to the repository:

- chore(sprint11): establish baseline and progress plan
- feat(template): add CTO and canonical skill templates
- feat(employees): persist configuration and enforce atomic hiring
- feat(api): expose employee hiring and configuration
- feat(dashboard): add employee hiring experience
- docs(sprint11): synchronize architecture and UX
- chore(sprint11): finalize progress and verification

Use conventional commits.

Push at phase checkpoints when safe.

At the end verify:

git status --short
git rev-parse HEAD
git rev-parse origin/master

The working tree must be clean unless a specific justified artifact is reported.

---

## 15. Final Report Format

Return one final report with these exact sections:

1. Commits
   - starting SHA
   - final SHA
   - origin/master SHA
   - ordered commit list
   - working-tree status

2. Sprint Result
   - objective achieved or not
   - completed item count
   - incomplete/blocked items

3. Repository Divergences
   - which assumptions in this brief were wrong
   - how implementation adapted
   - related DECISIONS entries

4. CTO Role
   - canonical definition
   - founding/vacancy behavior
   - singleton behavior
   - proof it is data-driven

5. Hiring Domain
   - service location
   - validation rules
   - transaction behavior
   - singleton concurrency guarantee
   - residual risks

6. Employee Configuration
   - persisted fields
   - mutable fields
   - immutable fields
   - model registry source
   - skill-template registry source
   - security constraints

7. API
   - endpoint list
   - auth/ownership behavior
   - error/status mapping
   - public schema and intentionally hidden fields

8. Dashboard UX
   - hiring flow
   - editing flow
   - singleton behavior
   - multiple Employee display
   - loading/error/success behavior

9. Resolver and Existing Behavior
   - how hired Employees participate
   - multi-employee deterministic result
   - existing mission lifecycle result

10. Migrations
    - previous revision → new revision
    - backfill behavior
    - fresh database result
    - rollback status if tested

11. Verification Matrix
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
    Each must be PASS, FAIL, or UNVERIFIED with evidence.

12. Tests
    - starting count
    - ending count
    - new test areas
    - modified existing tests
    - classification and reason for each modified test

13. Invariants and Security
    - Role/Employee separation
    - canonical registries
    - no role hardcoding
    - no arbitrary skills/tools
    - no free shell
    - no secret leakage
    - no silent failures
    - mock mode

14. Documentation
    - files updated
    - major decisions added
    - any remaining mismatch

15. Scope Control
    - work deliberately deferred to Sprint 12+
    - any accidental scope expansion and corrective action

16. Low-confidence Areas
    - files/behaviors requiring PM/CTO review
    - why confidence is low

17. Sprint 12 Handoff
    - exact organization capabilities now available
    - CTO-related planning capabilities still absent
    - architectural prerequisites for PM↔CTO planning
    - unresolved risks

18. Final State
    - tests
    - typecheck
    - build
    - migration
    - API E2E
    - browser status
    - mock E2E
    - remote HEAD
    - overall Sprint status

Do not say “100% complete” if any required DoD item is FAIL or an applicable required verification is missing.

Begin with Phase 0 and continue through Phase 5 without routine confirmation.
