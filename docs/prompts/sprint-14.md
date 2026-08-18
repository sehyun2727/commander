# Sprint 14 — Responsive CEO Workspace

Execute this sprint autonomously from Phase 0 through Phase 5.

Expected baseline:
- local HEAD: 88196f2
- origin/master: 88196f2
- backend baseline: 336 passed / 4 skipped
- dashboard typecheck/build: PASS
- fresh DB bootstrap and seed: PASS
- mock API E2E with zero provider keys: PASS
- browser interaction verification: UNVERIFIED

Repository and git state are authoritative. Verify all baseline claims first.

Follow the current CLAUDE.md, architecture, decisions, UX specification, security rules, progress discipline, verification standards, and reporting format.

Do not stop for routine confirmation. Stop only for a hard blocker, destructive ambiguity, security/cost exposure, or an irreconcilable product decision.

---

## 1. Goal

Turn Sprint 13’s workspace backend contract into the primary CEO operating surface.

At the end of Sprint 14, the CEO must be able to open one responsive Workspace and immediately understand:

1. Which company is active.
2. What is happening now.
3. What requires CEO attention.
4. What the recommended next action is.
5. Whether planning, specification review, execution, or company setup is blocked.
6. Which Employees are active, idle, unavailable, or missing.
7. What changed recently.
8. Where to navigate to complete the required action.

The Workspace must work coherently on desktop and mobile.

This sprint implements the shell and integrated workflow UX.

It does not implement customizable widgets, drag-and-drop dashboards, Agent Harness, self-correction, organizational memory, or new backend workflow domains.

---

## 2. Product Principles

### 2.1 Outcome before internals

The CEO should see:

- current outcome,
- blocker,
- decision required,
- recommended action,
- recent progress.

Do not lead with internal database objects, raw events, provider details, or agent implementation terminology.

### 2.2 One primary action

The server-derived `next_action` is the primary CTA.

The frontend must not rebuild lifecycle precedence.

The UI may provide secondary navigation, but it must not present several actions as equally urgent when the server has identified one priority.

### 2.3 Progressive disclosure

First view:

- current focus
- primary CTA
- important pending items
- concise organization status
- recent activity

Detailed information belongs in expandable sections or existing deep-linked pages.

Do not place full transcripts, complete specifications, or every historical mission on the initial screen.

### 2.4 Existing domain pages remain authoritative

The Workspace coordinates existing functionality.

Existing pages remain responsible for detailed actions such as:

- specification review and revision
- mission details
- approval decisions
- Employee hiring/configuration
- company settings

Do not duplicate complex mutation forms in the Workspace unless a current shared component can be reused safely.

### 2.5 Mobile is a first-class target

The Workspace must not merely shrink a desktop grid.

On small screens:

- content order must follow action priority,
- primary CTA must remain easy to reach,
- cards must stack cleanly,
- navigation must remain usable,
- long text must wrap safely,
- controls need suitable touch targets,
- no essential content may depend only on hover.

---

## 3. Required Repository Inspection

Before changing code, inspect at minimum:

- CLAUDE.md
- PROGRESS.txt
- README.md
- docs/ARCHITECTURE.md
- docs/DECISIONS.md, especially Sprint 12–13 decisions
- docs/design/UX_SPEC.md
- git history through 88196f2
- Sprint 13 workspace public schemas
- projection and next-action services
- workspace snapshot and event endpoints
- cursor/reconnect behavior
- current workspace proof page
- dashboard app shell and routing
- Sidebar and navigation components
- company/project selection flow
- React Query configuration, keys, hooks, and cache behavior
- SSE/event subscription implementation
- global toast/error components
- existing mission, specification, approval, and Employees pages
- shared card, badge, button, dialog, skeleton, empty-state, and error components
- responsive design tokens and CSS conventions
- accessibility and test tooling
- current frontend test setup, if any
- backend tests protecting workspace contracts

Reuse existing components and visual conventions where possible.

---

## 4. Approved Product Decisions

### 4.1 Workspace becomes the primary company landing page

For a selected company/project, the Workspace becomes the default operational destination.

Do not delete existing routes.

Preserve direct URLs and browser history behavior.

If the current route architecture has a safer additive path, introduce the Workspace first and redirect the company landing route only after verifying no loop or broken deep link occurs.

### 4.2 Shell structure

Use a responsive structure equivalent to:

Desktop:
- persistent or collapsible primary navigation
- top context/header
- main Workspace content
- optional compact secondary context area only where useful

Mobile:
- compact header
- accessible navigation drawer or bottom navigation, according to existing patterns
- single-column priority order
- primary action placed near the top
- no permanently visible wide Sidebar

Do not build a new design system.

### 4.3 Required Workspace sections

The Workspace must include:

1. Company context/header
2. Primary next-action panel
3. Current focus
4. Pending CEO attention
5. Planning/specification summary
6. Mission summary
7. Organization summary
8. Recent activity
9. Connection/freshness status

Exact card boundaries may adapt to current components.

This is a fixed product layout, not the Sprint 15 widget system.

### 4.4 Next-action mapping

Render the Sprint 13 server response directly.

For each supported action kind:

- show title and explanation from safe server data,
- select an approved visual treatment,
- navigate to the server-provided authorized target,
- handle unavailable/stale target safely,
- never construct authority from arbitrary external URLs.

Use an allowlisted internal-route mapper if route targets are not already strongly typed.

Unknown future action kinds must degrade safely:

- show a generic attention state,
- allow refresh,
- avoid crashing,
- avoid guessing a destructive action.

### 4.5 Pending actions

Show concise pending items, ordered by server priority.

Do not duplicate the server precedence algorithm.

Each item should include:

- type
- short reason
- relevant status
- target deep link
- whether CEO input is required

Apply a bounded visible count and provide “view all” navigation where an existing page supports it.

### 4.6 Activity is summarized

Show safe activity summaries from Sprint 13.

Required behavior:

- stable ordering
- duplicate-safe updates
- clear actor/role label where safe
- timestamp presentation
- event/status distinction
- bounded list
- empty state
- deep link when available

Do not render raw event payloads or hidden reasoning.

### 4.7 Connection and freshness

The CEO must be able to distinguish:

- live
- reconnecting
- stale/degraded
- offline/error
- last updated time

Reconnect must use Sprint 13 semantics.

When event continuity is uncertain:

- refetch a fresh snapshot,
- avoid silently showing stale data,
- preserve a usable read-only view when possible.

### 4.8 Company switching

Changing active company/project must:

- cancel or isolate old queries/subscriptions,
- clear stale Workspace state,
- establish a new cursor/subscription,
- never flash another company’s data,
- preserve auth and ownership behavior,
- update URL/context according to existing routing conventions.

### 4.9 No generic Workspace mutation dispatcher

Do not add a generic action mutation.

Workspace CTAs route to or invoke existing typed domain actions only.

Prefer navigation to existing authoritative pages for complex actions.

### 4.10 Browser verification honesty

First inspect whether usable browser automation exists in the environment.

If it exists, perform interactive verification.

If unavailable:

- record exactly what was checked,
- use component tests/typecheck/build/API verification as applicable,
- mark browser interaction `UNVERIFIED`,
- do not claim visual, keyboard, responsive, or click-through validation as PASS.

---

## 5. Information Architecture

Preferred visual order:

### Desktop

1. Header/company context
2. Primary action
3. Current focus and pending attention
4. Planning/specification and missions
5. Organization and recent activity

### Mobile

1. Company context
2. Primary action
3. Pending CEO attention
4. Current focus
5. Planning/specification
6. Missions
7. Organization
8. Recent activity
9. Connection status

The exact order may change based on repository UX conventions, but action priority must remain clear.

---

## 6. State Requirements

The Workspace must explicitly handle:

### Initial loading
- meaningful skeletons
- no false empty-state flash

### Empty company
- explain that there is no active work
- provide the valid next setup/start path

### Active planning
- show current planning state
- link to specification/planning detail

### Clarification required
- make CEO input prominent
- navigate to the clarification surface

### Specification review
- show version/status
- navigate to authoritative review page

### Approved and ready
- show execution readiness
- route to the existing supported start action

### Active mission
- show concise progress/status
- link to mission details

### Company setup required
- show missing CTO or other supported setup issue
- route to Employees/Organization

### Failure
- show safe actionable error summary
- provide retry/detail path only when supported

### Reconnecting or stale
- retain safe cached content where appropriate
- show status visibly
- trigger bounded recovery

### Unauthorized/not found
- use existing auth/not-found behavior
- do not leak company existence

### Unknown action or event type
- degrade safely without crashing

---

## 7. Frontend Architecture Requirements

### 7.1 Typed server contract

Use generated or explicit TypeScript types matching the backend contract.

Do not redefine status/action enums independently in multiple components.

Centralize safe presentation mapping for:

- action kind → icon/color/label
- lifecycle status → badge treatment
- connection state → text/indicator

Presentation mapping may be frontend-owned; business precedence must remain server-owned.

### 7.2 Query and subscription lifecycle

Use one canonical Workspace query key per company/project.

Requirements:

- old company data does not bleed into new context,
- event updates are duplicate-safe,
- reconnect triggers correct invalidation/refetch,
- unmount cleans up subscriptions,
- repeated renders do not open duplicate connections,
- stale target causes safe refresh,
- network errors do not create retry storms.

### 7.3 Component boundaries

Prefer small domain-oriented components, for example:

- WorkspaceHeader
- NextActionPanel
- CurrentFocusCard
- PendingAttentionList
- PlanningSummary
- MissionSummary
- OrganizationSummary
- RecentActivity
- ConnectionStatus

Adapt names to repository conventions.

Do not place the entire Workspace in one oversized page component.

### 7.4 Accessibility

At minimum:

- semantic headings
- keyboard-operable navigation and controls
- visible focus
- labeled icon buttons
- status not represented by color alone
- live connection changes announced without excessive noise
- sensible reading order
- dialog/drawer focus management
- reduced-motion compatibility where animation exists
- touch targets appropriate for mobile

### 7.5 Performance

Avoid:

- duplicate snapshot fetches
- one query per card
- unnecessary full-page rerenders on every event
- rendering unbounded activity
- loading full domain detail into the Workspace
- large client-side policy calculations

Use memoization only where actual rerender behavior justifies it.

---

## 8. Backend Scope

Backend changes should be minimal and limited to contract defects discovered during real UI integration.

Allowed:

- correcting missing safe fields required by the approved Workspace layout
- tightening schemas
- fixing cursor/reconnect defects
- fixing deep-link typing
- adding narrowly required tests
- fixing auth or consistency defects

Not allowed:

- redesigning the projection architecture
- new business workflow domains
- generic mutation APIs
- widget persistence
- notification system
- analytics infrastructure

Record any contract change and maintain backward compatibility where practical.

---

## 9. Testing Requirements

Use existing frontend testing tools. If none exist, do not introduce a large testing framework without justification.

Required automated coverage where supported:

- next-action rendering
- unknown action fallback
- deep-link mapping
- pending-item ordering as received
- loading state
- empty state
- failure/degraded state
- connection-state rendering
- duplicate event handling
- company switch isolation
- reconnect/refetch behavior
- activity bounds
- no raw payload rendering
- responsive structural behavior through available component/CSS testing
- accessibility checks supported by current tooling

Required backend regression coverage for any changed contract.

Do not rely only on snapshots of generated HTML.

Do not weaken existing tests.

---

## 10. Phases

## Phase 0 — Baseline and UX Audit

1. Verify local HEAD, origin/master, and working tree.
2. Run baseline backend tests.
3. Run dashboard typecheck and production build.
4. Verify Sprint 13 workspace API and mock lifecycle.
5. Determine whether browser automation is actually available.
6. Audit the current shell, Sidebar, routes, responsive conventions, and shared components.
7. Audit Workspace proof page and identify reusable code.
8. Map every server `next_action` kind to an existing safe destination.
9. Identify unsupported or stale-target cases.
10. Define desktop/mobile information architecture.
11. Define query/subscription lifecycle.
12. Replace PROGRESS.txt with Sprint 14 live checklist.
13. Record non-obvious decisions.
14. Commit/push the Phase 0 checkpoint if consistent with repository practice.

## Phase 1 — Responsive Shell and Navigation

1. Implement or adapt the responsive application shell.
2. Preserve existing routes and deep links.
3. Make Workspace the primary company landing destination safely.
4. Add desktop navigation behavior.
5. Add mobile navigation behavior.
6. Implement company context/header.
7. Implement accessible navigation controls.
8. Ensure active route indication.
9. Ensure browser history and direct-link behavior.
10. Ensure company switching isolates state.
11. Add targeted tests.
12. Run typecheck/build.
13. Update PROGRESS.txt.
14. Commit/push Phase 1.

## Phase 2 — Core Workspace Sections

1. Build primary next-action panel.
2. Build current-focus section.
3. Build pending-attention section.
4. Build planning/specification summary.
5. Build mission summary.
6. Build organization summary.
7. Build recent-activity section.
8. Build connection/freshness indicator.
9. Implement safe internal deep-link mapping.
10. Implement unknown action/event fallback.
11. Reuse server priority and bounded summaries.
12. Avoid raw payload or internal-reasoning rendering.
13. Add component/behavior tests supported by the repository.
14. Run typecheck/build.
15. Update PROGRESS.txt.
16. Commit/push Phase 2.

## Phase 3 — Live Updates and State Integrity

1. Connect Sprint 13 snapshot hook to the Workspace.
2. Integrate incremental activity/SSE.
3. Prevent duplicate subscriptions.
4. Apply duplicate-safe event handling.
5. Refetch snapshot after authoritative changes.
6. Implement reconnect with bounded retry.
7. Implement gap/invalid-cursor recovery.
8. Show live/reconnecting/stale/offline state.
9. Preserve safe cached view during transient failure.
10. Verify company switching closes old subscriptions.
11. Verify stale targets trigger recovery.
12. Add tests for connection and isolation behavior.
13. Run API-level live walkthrough.
14. Update PROGRESS.txt.
15. Commit/push Phase 3.

## Phase 4 — Responsive, Accessibility, and Workflow Polish

1. Verify desktop layout at representative widths.
2. Verify tablet and mobile layouts at representative widths.
3. Fix overflow, wrapping, spacing, and touch targets.
4. Verify keyboard navigation.
5. Verify focus order and visible focus.
6. Verify navigation drawer/dialog focus behavior.
7. Verify semantic headings and labels.
8. Verify status is not color-only.
9. Verify loading, empty, error, degraded, and unknown states.
10. Verify all CTAs reach authoritative existing pages.
11. Ensure no duplicated lifecycle policy exists in frontend.
12. Run typecheck.
13. Run production build.
14. Run supported accessibility/component tests.
15. Perform browser interaction verification if tooling exists.
16. Otherwise mark visual/click/keyboard/responsive browser checks UNVERIFIED.
17. Update PROGRESS.txt.
18. Commit/push Phase 4.

## Phase 5 — Regression, Audit, and Documentation

1. Run full backend tests.
2. Run all frontend tests that exist.
3. Run dashboard typecheck.
4. Run dashboard production build.
5. Verify migration chain and fresh bootstrap if backend/schema changed.
6. Run mock E2E with zero provider keys.
7. Verify Workspace states across:
   - empty/setup
   - planning
   - clarification
   - specification review
   - approved-ready
   - active mission
   - failure/cancellation
8. Verify company isolation and auth behavior.
9. Verify company-switch state isolation.
10. Verify reconnect/refetch behavior.
11. Audit all next-action targets.
12. Audit frontend for lifecycle precedence duplication.
13. Audit event rendering for hidden reasoning/secrets.
14. Audit response/activity bounds.
15. Audit responsive overflow through available tooling.
16. Inspect complete diff for scope leakage.
17. Update:
   - CLAUDE.md
   - PROGRESS.txt
   - README.md when navigation/user workflow changed
   - docs/ARCHITECTURE.md
   - docs/DECISIONS.md
   - docs/design/UX_SPEC.md
18. Record Sprint 15 boundaries and deferrals.
19. Commit/push final documentation.
20. Verify intended clean working tree.
21. Verify local HEAD equals origin/master.

---

## 11. Definition of Done

Sprint 14 is complete only when:

1. Baseline is verified.
2. Workspace is the primary selected-company landing surface.
3. Existing routes and deep links remain functional.
4. Desktop navigation works through available verification.
5. Mobile navigation is structurally implemented.
6. Company context is clear.
7. Primary server-derived next action is prominent.
8. Frontend does not recalculate business precedence.
9. Unknown actions degrade safely.
10. Pending CEO attention is visible and bounded.
11. Planning/specification state is visible.
12. Mission state is visible.
13. Organization availability is visible.
14. Recent activity is safe and bounded.
15. Connection freshness is visible.
16. Snapshot query is company-scoped.
17. Company switching does not leak stale data.
18. Duplicate subscriptions are prevented.
19. Duplicate events are safe.
20. Reconnect is bounded.
21. Cursor gaps recover through refetch.
22. Stale targets recover safely.
23. Empty state is actionable.
24. Failure/degraded states are visible.
25. Unauthorized/not-found behavior does not leak data.
26. Existing typed domain actions remain authoritative.
27. No generic Workspace mutation endpoint is added.
28. Workspace components have clear boundaries.
29. Controls have accessible labels and keyboard semantics.
30. Status is not conveyed by color alone.
31. Mobile layout does not depend on hover.
32. No hidden reasoning, raw payloads, provider secrets, or unsafe tool data are rendered.
33. Existing planning/specification/mission/hiring flows remain functional.
34. Full backend suite passes.
35. Frontend tests pass where present.
36. Dashboard typecheck passes.
37. Dashboard production build passes.
38. Mock E2E works with zero provider keys.
39. Browser verification is honestly reported.
40. Documentation matches implementation.
41. No Sprint 15+ widget architecture leaks into the sprint.
42. Final commits are pushed.
43. Local HEAD equals origin/master.

Do not mark complete when a required applicable item fails.

---

## 12. Out of Scope

Do not implement:

- user-configurable widgets
- widget registry/framework
- drag-and-drop layout
- saved personal layouts
- analytics dashboards
- notification center
- global search
- Agent Harness
- unrestricted tool execution
- free shell
- self-correction loop
- organizational memory
- multi-user collaboration
- billing
- broad provider expansion
- cloud deployment work
- new business workflow domains
- duplicated specification/approval/hiring forms inside Workspace
- generic action dispatcher
- replacement of all existing detail pages
- final visual brand redesign

Record future requirements without implementing them.

---

## 13. Final Report

Return one evidence-based report containing:

1. Starting/final/origin SHA and working-tree state
2. Sprint result and completed checklist/DoD count
3. Commits
4. Repository divergences
5. Workspace route and shell
6. Desktop/mobile navigation
7. Information architecture
8. Next-action and deep-link mapping
9. Workspace sections and state handling
10. Query, subscription, reconnect, and company-switch behavior
11. Accessibility review
12. Responsive review
13. Backend contract changes, if any
14. Verification matrix:
    - backend tests
    - frontend tests
    - API/live walkthrough
    - typecheck
    - build
    - browser
    - accessibility
    - responsive
    - mock E2E
15. Starting/ending test counts and modified-test classification
16. Security/privacy audit
17. Existing-feature compatibility
18. Documentation updates
19. Scope control and Sprint 15 deferrals
20. Low-confidence areas
21. Sprint 15 handoff
22. Final state

Begin with Phase 0 and continue through Phase 5 without routine confirmation.
