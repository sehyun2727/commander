# Sprint 15 — Safe CEO Workspace Widget System

Execute this sprint autonomously from Phase 0 through Phase 5.

Expected baseline:
- local HEAD: 45bcf11
- origin/master: 45bcf11
- backend baseline: 336 passed / 4 skipped
- dashboard typecheck/build: PASS
- Sprint 14 was frontend-only
- browser-rendered interaction verification: UNVERIFIED

Repository and git state are authoritative. Verify all baseline claims first.

Follow the current CLAUDE.md, architecture, decisions, UX specification, security requirements, progress discipline, verification standards, and reporting format.

Do not stop for routine confirmation. Stop only for a hard blocker, destructive ambiguity, security/cost exposure, or irreconcilable architecture decision.

---

## 1. Goal

Convert Sprint 14’s fixed CEO Workspace composition into a safe, typed, configurable widget system.

At the end of Sprint 15:

1. Existing Workspace sections are represented by first-party widget definitions.
2. Widget types come from a canonical server-owned allowlist.
3. The CEO can reorder supported widgets.
4. The CEO can hide and restore optional widgets.
5. Required widgets remain protected.
6. Preferences persist per user and company/project.
7. Desktop and mobile layouts remain coherent.
8. Unknown, obsolete, or malformed widget settings degrade safely.
9. One widget failure cannot crash the entire Workspace.
10. Existing snapshot, next-action, SSE, auth, and company isolation remain intact.
11. Mock mode continues to require zero provider keys.

This sprint builds a first-party widget composition system.

It does not allow third-party plugins, executable widgets, arbitrary data sources, custom code, free-form queries, or unrestricted layout scripting.

---

## 2. Product Outcome

The CEO should be able to personalize information density without changing business rules.

Supported actions:

- enter layout-edit mode,
- reorder widgets,
- hide optional widgets,
- restore hidden widgets,
- reset to the product default,
- preserve preferences after refresh,
- maintain separate preferences across companies.

The CEO must not be able to:

- hide the primary next action,
- change server lifecycle precedence,
- create arbitrary widgets,
- enter HTML or JavaScript,
- configure arbitrary API endpoints,
- expose another company’s data,
- break mobile reading order,
- create an unusable empty Workspace.

---

## 3. Required Repository Inspection

Before changing code, inspect at minimum:

- CLAUDE.md
- PROGRESS.txt, including Sprint 15 handoff and low-confidence areas
- README.md
- docs/ARCHITECTURE.md
- docs/DECISIONS.md, especially #223–227
- docs/design/UX_SPEC.md
- git history through 45bcf11
- Sprint 13 workspace public schemas and projection service
- Sprint 14 Workspace page and component tree
- responsive shell, mobile drawer, focus management, and navigation
- snapshot query and SSE lifecycle
- next-action route mapping
- company/project context switching
- authentication and company-ownership patterns
- current user/account model
- existing user settings/preferences patterns, if any
- Alembic migration history
- global error handling
- frontend test tooling and package dependencies
- CSS/layout conventions
- existing drag-and-drop or sortable dependencies, if any
- mock lifecycle tests

Do not introduce a new dependency until confirming the repository does not already provide the required capability.

---

## 4. Approved Product Decisions

### 4.1 First-party registry only

Use one canonical server-owned widget registry.

Each widget definition should contain typed immutable metadata equivalent to:

- key
- title
- description
- category
- required
- default visibility
- default order
- minimum supported size where relevant
- maximum supported size where relevant
- supported contexts
- data requirement identifier
- schema/config version

Use the smallest field set actually required.

The client may maintain presentation-component mapping by widget key, but it must not independently define which widget keys are valid or configurable.

### 4.2 Initial widgets

Represent Sprint 14 sections as widgets equivalent to:

- primary next action
- current focus
- pending CEO attention
- planning/specification
- missions
- organization
- recent activity
- connection/freshness

After inspecting the existing UI, combine or separate widgets only when product meaning and responsive behavior justify it.

### 4.3 Required widgets

At minimum, these should remain non-hideable unless repository UX proves a safer alternative:

- primary next action
- connection/freshness status

The default layout must always provide a useful Workspace.

Do not let all meaningful widgets be hidden.

### 4.4 Preferences are configuration, not business state

Widget preferences control presentation only.

They must not:

- alter `next_action`,
- alter pending-action priority,
- advance workflows,
- mutate Missions or Specifications,
- change Employee state,
- modify event ordering,
- bypass auth,
- become a second source of workspace business truth.

### 4.5 Preference ownership

Persist preferences per authenticated user and company/project.

The same user may have different layouts for different companies.

Different users must not share layouts unless explicitly supported by an existing team-settings model.

Never trust a user ID supplied directly by the client; derive the user from authentication.

### 4.6 Server validation

The server validates:

- company ownership,
- widget key allowlist,
- required-widget presence,
- uniqueness,
- supported visibility,
- legal order values,
- legal size/configuration,
- version compatibility,
- bounded payload size.

Frontend validation is convenience only.

### 4.7 Optimistic concurrency

Prevent one browser tab from silently overwriting a newer layout from another tab.

Use the smallest coherent mechanism compatible with the repository, such as:

- revision integer,
- ETag/If-Match,
- updated_at precondition.

A stale update should return structured `409 Conflict` or equivalent.

The UI must visibly offer reload/retry rather than silently overwriting.

### 4.8 Versioning and normalization

Preferences require a schema version.

When:

- a new widget is introduced,
- a widget is retired,
- stored order is incomplete,
- duplicate keys exist,
- an unknown key is present,
- configuration is malformed,

normalize safely:

- preserve valid user choices,
- drop or quarantine unsupported keys,
- restore required widgets,
- append newly introduced default widgets deterministically,
- avoid crashing,
- return a normalized authoritative representation.

Do not execute or dynamically import unknown widget keys.

### 4.9 Responsive layout model

Prefer a simple ordered layout over a complex free-placement grid.

Recommended:

- desktop: ordered sections with limited supported widths/spans if already needed
- mobile: one-column order derived from the same canonical order
- required high-priority widget remains near the top
- hidden state applies consistently

Do not implement arbitrary x/y pixel placement.

Do not add drag-and-drop if accessible controls can meet the requirement more safely. If drag-and-drop is used, keyboard alternatives are mandatory.

### 4.10 Editing UX

Provide a clear edit mode.

Required controls:

- move up/down or accessible sortable equivalent,
- hide optional widget,
- restore hidden widget,
- reset to default,
- save/cancel or reliable autosave with visible status,
- conflict handling,
- validation errors,
- loading and saving states.

Normal Workspace viewing must remain uncluttered.

### 4.11 Failure isolation

A component/rendering failure in one optional widget must not destroy the entire Workspace.

Use a scoped error boundary or equivalent isolation strategy.

The failed widget should show:

- concise safe error state,
- retry/refetch where meaningful,
- no raw stack trace,
- no secret-bearing payload.

The primary next-action widget requires a stronger fallback: if it cannot render, provide a safe refresh/degraded state rather than removing the CEO’s main action silently.

### 4.12 Existing backend snapshot remains canonical

Reuse Sprint 13’s bounded workspace snapshot.

Do not add one backend endpoint per widget unless a proven performance or permission requirement exists.

Do not allow widgets to name arbitrary API routes or queries.

### 4.13 No plugin system

This sprint explicitly excludes:

- third-party widget packages,
- uploaded widget bundles,
- arbitrary component paths,
- JavaScript/HTML/CSS input,
- iframe widgets,
- arbitrary URLs,
- arbitrary SQL/filter expressions,
- arbitrary API endpoint selection,
- marketplace behavior.

---

## 5. Target Data Model

Adapt to repository conventions.

A preference record should conceptually include:

- ID
- authenticated user ownership
- company/project ownership
- schema version
- revision/version
- ordered widget entries
- created_at
- updated_at

Each entry should include only allowlisted configuration, for example:

- widget_key
- visible
- order
- supported size/span, if approved

Prefer typed JSON for the small ordered layout only if validation and migration semantics are strong.

Prefer normalized rows if the current database or update patterns make that safer.

Document the choice and trade-offs.

Use a uniqueness constraint equivalent to one active preference set per user and company/project.

---

## 6. API Requirements

Add a small typed API surface following current conventions.

Required capabilities:

1. Get available widget registry metadata.
2. Get effective preferences for current user/company.
3. Update preferences with optimistic-concurrency protection.
4. Reset preferences to current defaults.

The effective-preferences response should already be normalized.

Potential route shape, adapted to repository conventions:

- GET `/api/projects/{id}/workspace/widgets`
- GET `/api/projects/{id}/workspace/preferences`
- PUT `/api/projects/{id}/workspace/preferences`
- DELETE or POST reset endpoint for preferences

Do not accept client-supplied user ownership.

Required structured failures:

- unauthenticated
- company not found/not owned
- malformed payload
- unknown widget
- required widget hidden or missing
- duplicate widget
- invalid configuration
- stale revision conflict
- oversized payload

Use 4xx responses, not 500, for expected validation/conflict cases.

---

## 7. Frontend Requirements

### 7.1 Registry-driven composition

The Workspace should render widgets from:

- server registry/effective preferences,
- a safe local component map for approved widget keys,
- existing Sprint 14 components.

Unknown keys must never be dynamically executed.

If registry metadata contains an unknown key with no bundled component:

- do not crash,
- show a safe unsupported-widget notice in edit mode,
- omit or degrade safely in normal mode,
- report through observability without leaking internals.

### 7.2 Edit mode

Implement a distinct edit experience.

Required:

- accessible entry/exit
- current visible order
- hidden-widget tray/list
- reorder controls
- hide/restore controls
- reset confirmation
- save/cancel or visible autosave
- dirty-state handling
- stale-write conflict handling
- navigation protection if unsaved changes would be lost, where consistent with current patterns

### 7.3 Optimistic update behavior

If using optimistic UI:

- keep a rollback snapshot,
- rollback on server rejection,
- show global error visibility,
- refetch authoritative normalized preferences,
- do not leave the UI in a locally impossible state.

Avoid retry storms on `409 Conflict`.

### 7.4 Company switching

On company change:

- isolate preference query keys,
- discard or resolve unsaved changes safely,
- load the target company’s effective layout,
- do not flash the previous company’s layout or data,
- keep Sprint 14 snapshot/SSE cleanup guarantees.

### 7.5 Accessibility

Every reorder operation must be keyboard-operable.

If using drag-and-drop:

- provide move up/down alternatives,
- provide clear accessible labels,
- maintain focus after movement,
- announce changed position,
- meet touch target requirements.

Hide/restore/reset must be operable without pointer input.

### 7.6 Responsive behavior

- desktop arrangement follows validated order
- mobile collapses into one column
- primary next action remains high priority
- hidden widgets remain hidden
- controls do not overflow
- no essential interaction depends only on drag
- edit mode remains usable at narrow widths

---

## 8. Security Requirements

- Registry is server-owned and allowlisted.
- Derive user identity from authentication.
- Enforce company ownership on all preference routes.
- Reject unknown widget keys.
- Reject executable fields and arbitrary URLs.
- Bound entry count and payload size.
- Prevent mass assignment.
- Do not expose hidden reasoning, provider data, secrets, or raw event payloads.
- Do not allow widget configuration to select API endpoints.
- Do not dynamically import from client-provided strings.
- Preserve Rule #15 not-found behavior where applicable.
- Deep links remain existing allowlisted internal routes.
- Error states do not expose stack traces.
- Preference updates cannot mutate business state.
- Audit events should contain safe metadata only.

---

## 9. Observability

Emit or log safe preference lifecycle information consistent with current architecture:

- initialized/default effective layout
- updated layout
- reset layout
- stale-write conflict
- normalization applied
- unsupported stored widget dropped

Do not emit the entire preference payload if unnecessary.

Useful safe fields:

- user ID if current logging policy permits
- company/project ID
- old/new revision
- changed widget keys
- normalization reason
- outcome

Do not add a broad analytics system.

---

## 10. Phases

## Phase 0 — Baseline and Architecture Decision

1. Verify local HEAD, origin/master, and working tree.
2. Run backend baseline.
3. Run dashboard typecheck/build.
4. Verify Sprint 14 live Workspace API/SSE flow.
5. Inspect Sprint 15 handoff and low-confidence areas.
6. Audit user/auth/company ownership models.
7. Audit current settings/preferences patterns.
8. Audit frontend dependencies and accessible reorder options.
9. Decide persistence structure.
10. Decide concurrency strategy.
11. Decide registry schema.
12. Decide required/optional widgets.
13. Decide edit/save behavior.
14. Decide responsive ordering rules.
15. Replace PROGRESS.txt with Sprint 15 live checklist.
16. Record non-obvious decisions.
17. Commit/push Phase 0 if consistent with repository practice.

## Phase 1 — Registry, Persistence, and Validation

1. Implement canonical immutable widget registry.
2. Define typed public registry schemas.
3. Add preference persistence model.
4. Add schema version and revision.
5. Add uniqueness and ownership constraints.
6. Add Alembic migration.
7. Implement default generation.
8. Implement normalization.
9. Implement validation:
   - known keys
   - uniqueness
   - required widgets
   - visibility
   - order
   - size/configuration
   - payload bounds
10. Implement optimistic-concurrency domain behavior.
11. Add tests for:
    - registry immutability
    - default layout
    - malformed/unknown entries
    - required-widget restoration/rejection
    - duplicate keys
    - newly added widget normalization
    - retired widget normalization
    - stale revision conflict
    - user/company uniqueness
    - concurrent first creation/update
12. Verify migration from Sprint 14 and fresh DB.
13. Update PROGRESS.txt.
14. Commit/push Phase 1.

## Phase 2 — Preferences API and Isolation

1. Add widget-registry endpoint.
2. Add effective-preference endpoint.
3. Add update endpoint.
4. Add reset endpoint.
5. Apply auth and company ownership.
6. Derive user identity from auth.
7. Return normalized authoritative preferences.
8. Map expected validation errors to structured 4xx.
9. Map stale revision to 409 or repository-equivalent conflict.
10. Add safe observability.
11. Add API/integration tests for:
    - default read
    - valid update
    - reset
    - persistence after reload
    - company-specific layout
    - user-specific layout
    - cross-company denial
    - unauthenticated access
    - unknown widget
    - required widget hidden
    - duplicate widget
    - stale update
    - oversized payload
    - no business-state mutation
12. Run live API walkthrough in mock mode.
13. Update PROGRESS.txt.
14. Commit/push Phase 2.

## Phase 3 — Registry-Driven Workspace and Edit Mode

1. Convert Sprint 14 fixed sections to registry-driven composition.
2. Reuse existing widget components.
3. Add safe component map.
4. Add effective-preference queries/hooks.
5. Add distinct edit mode.
6. Add reorder controls.
7. Add hide/restore controls.
8. Add reset-to-default.
9. Add save/cancel or approved autosave behavior.
10. Add dirty/saving/success/error states.
11. Add stale-write conflict UX.
12. Add optimistic rollback if optimistic updates are used.
13. Add company-switch preference isolation.
14. Prevent required-widget removal.
15. Prevent arbitrary dynamic imports.
16. Add targeted tests supported by existing tooling.
17. Run typecheck/build.
18. Update PROGRESS.txt.
19. Commit/push Phase 3.

## Phase 4 — Failure Isolation, Responsive, and Accessibility

1. Add per-widget error isolation.
2. Add stronger next-action fallback.
3. Add unsupported-widget fallback.
4. Verify focus preservation after reorder.
5. Add screen-reader position announcements where supported.
6. Verify keyboard-only reorder/hide/restore/reset.
7. Verify mobile edit mode.
8. Verify touch-sized controls.
9. Verify desktop and mobile ordering.
10. Verify company switching.
11. Verify no cross-company layout/data flash.
12. Verify navigation with unsaved changes.
13. Verify reset confirmation.
14. Verify loading/empty/error/conflict states.
15. Run typecheck.
16. Run production build.
17. Run available frontend/accessibility tests.
18. Perform browser interaction verification if tooling exists.
19. Otherwise record interactive drag/click/touch/visual checks as UNVERIFIED.
20. Update PROGRESS.txt.
21. Commit/push Phase 4.

## Phase 5 — Regression, Security Audit, and Documentation

1. Run full backend tests.
2. Run frontend tests that exist.
3. Run dashboard typecheck.
4. Run dashboard production build.
5. Verify Sprint 14→15 migration.
6. Verify fresh DB bootstrap and seed.
7. Run mock E2E with zero provider keys.
8. Verify default, update, refresh, reset, and conflict flows.
9. Verify two-company preference isolation.
10. Verify two-user isolation if test architecture supports multiple users.
11. Verify Workspace snapshot/SSE behavior remains intact.
12. Verify next-action policy remains server-owned.
13. Audit registry allowlist and dynamic import behavior.
14. Audit payload bounds and mass assignment.
15. Audit auth and Rule #15 behavior.
16. Audit hidden-reasoning/secret/raw-payload exposure.
17. Audit per-widget failure containment.
18. Audit migration and normalization behavior.
19. Inspect complete diff for scope leakage.
20. Update:
    - CLAUDE.md
    - PROGRESS.txt
    - README.md if user workflow changed
    - docs/ARCHITECTURE.md
    - docs/DECISIONS.md
    - docs/design/UX_SPEC.md
21. Record Sprint 16 boundaries and deferrals.
22. Commit/push final documentation.
23. Verify clean working tree.
24. Verify local HEAD equals origin/master.

---

## 11. Required Behavioral Tests

Required coverage:

- canonical registry
- registry immutability
- default effective preferences
- preference persistence
- per-user ownership
- per-company ownership
- unauthenticated denial
- cross-company denial
- Rule #15 behavior
- unknown widget rejection
- duplicate widget rejection
- required widget protection
- all-optional-hidden safe behavior
- invalid order/configuration
- payload bounds
- schema version handling
- normalization of old/unknown/retired entries
- deterministic insertion of new default widgets
- stale revision conflict
- concurrent first creation/update
- reset behavior
- no business-state mutation
- safe component mapping
- unsupported widget fallback
- one-widget failure isolation
- primary-action fallback
- keyboard reorder controls
- focus retention
- company switching isolation
- no stale layout/data flash
- optimistic rollback if used
- snapshot/SSE regression
- typecheck/build
- migration upgrade and fresh bootstrap
- mock E2E with zero keys

Do not weaken existing tests.

---

## 12. Definition of Done

Sprint 15 is complete only when:

1. Baseline is verified.
2. Widget registry is canonical, typed, immutable, and server-owned.
3. Only first-party allowlisted widgets are supported.
4. Existing Workspace sections render through the registry.
5. Preferences persist per authenticated user and company.
6. Client cannot choose another user’s preference owner.
7. Company ownership is enforced.
8. One active preference set exists per user/company.
9. Preferences have schema versioning.
10. Preferences have optimistic-concurrency protection.
11. Stale writes return a visible conflict.
12. Effective preferences are normalized safely.
13. Unknown stored widgets cannot execute.
14. Required widgets cannot be hidden or removed.
15. New default widgets are introduced deterministically.
16. Retired widgets do not crash existing users.
17. Payload size and entry count are bounded.
18. CEO can reorder widgets.
19. CEO can hide optional widgets.
20. CEO can restore hidden widgets.
21. CEO can reset to default.
22. Changes survive refresh.
23. Different companies can have different layouts.
24. Different users are isolated where supported.
25. Mobile uses a coherent single-column order.
26. Reordering is keyboard-operable.
27. Pointer-only drag is not required.
28. Focus is preserved sensibly.
29. One optional widget failure does not crash the Workspace.
30. Primary next-action has a safe degraded fallback.
31. Snapshot remains the canonical business-data source.
32. Frontend does not recreate next-action precedence.
33. No arbitrary endpoint/query/component configuration exists.
34. No dynamic import uses client-controlled paths.
35. No executable HTML/JS/CSS/plugin input exists.
36. Auth and Rule #15 behavior remain correct.
37. No secrets, hidden reasoning, or unsafe event payloads are exposed.
38. Existing Sprint 14 responsive shell remains functional.
39. Existing snapshot/SSE flow remains functional.
40. Backend full suite passes.
41. Frontend tests pass where present.
42. Dashboard typecheck passes.
43. Dashboard production build passes.
44. Migration upgrade passes.
45. Fresh bootstrap passes.
46. Mock E2E works with zero provider keys.
47. Browser verification is honestly reported.
48. Documentation matches implementation.
49. Sprint 16+ functionality did not leak into scope.
50. Final commits are pushed and local HEAD equals origin/master.

Do not claim completion if a required applicable item fails.

---

## 13. Out of Scope

Do not implement:

- third-party widgets
- plugin marketplace
- uploaded widget bundles
- arbitrary JavaScript, HTML, or CSS
- arbitrary URLs, API endpoints, SQL, or query expressions
- iframe widgets
- user-authored widgets
- drag-and-drop free-placement canvas
- arbitrary x/y pixel layout
- analytics warehouse
- notification center
- global search
- Agent Harness
- unrestricted tool execution
- free shell
- self-correction loop
- organizational memory
- multi-user collaboration features
- shared team layouts unless already supported
- billing
- broad provider expansion
- cloud deployment work
- new business workflow domains
- redesign of Sprint 13 projection
- duplication of domain mutation forms inside widgets

Record future requirements without implementing them.

---

## 14. Final Report

Return one evidence-based report containing:

1. Starting/final/origin SHA and working-tree state
2. Sprint result and checklist/DoD count
3. Commits
4. Repository divergences
5. Widget registry
6. Persistence and schema versioning
7. Normalization behavior
8. Optimistic-concurrency guarantee
9. API/auth/ownership behavior
10. Registry-driven frontend composition
11. Edit/reorder/hide/restore/reset UX
12. Company/user isolation
13. Responsive and accessibility review
14. Failure isolation
15. Snapshot/SSE compatibility
16. Security audit
17. Migration/bootstrap
18. Verification matrix
19. Starting/ending tests and modified-test classification
20. Documentation updates
21. Scope control and Sprint 16 deferrals
22. Low-confidence areas
23. Sprint 16 handoff
24. Final state

Begin with Phase 0 and continue through Phase 5 without routine confirmation.
