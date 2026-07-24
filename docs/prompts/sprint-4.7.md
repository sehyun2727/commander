# MISSION: Commander Sprint 4.7 — Headquarters UX

Read `CLAUDE.md` and **`docs/design/UX_SPEC.md`** first. The UX spec is the source of truth for this sprint — section references below (§) point into it. All architecture rules and the PROGRESS.txt discipline apply. Work autonomously start to finish; do NOT pause for confirmation between phases; log judgment calls in `docs/DECISIONS.md` ("Sprint 4.7"); commit per phase. Prerequisite: Sprint 4.5 merged (`b8e4556`), 56/56 tests green.

**Sprint goal:** apply the UX spec's core to the product — the CEO experience becomes legible, decision-first, and trustworthy — plus the invisible internal-template refactor (§10.6) that makes the architecture organization-ready without any UI change.

Reset `PROGRESS.txt` for this sprint from Appendix A before any feature work (same markers and per-item discipline as Sprint 4.5; archive nothing — the file is per-sprint, git history keeps the old one).

---

## Phase 1 — Backend Foundations

**1a. Internal template refactor (§10.6 — zero UI change).** Extract the founding trio, workflow role order, role contracts, and default profiles into ONE internal template data file (e.g. `apps/api/app/templates/software_company.py` or `.yaml` — your call). Founding and the workflow engine read from it; no component or route may branch on hardcoded role names that the template already provides. One template, no picker, no new API. Behavior must be byte-for-byte identical — existing tests prove it.

**1b. Structured decision content (§3.6).** The DecisionCard needs Problem / Recommendation / Risk / Impact. Extend the Reviewer's role contract (in the template file now) to emit, BEFORE the Verdict line, four labeled sections: `**Problem:**`, `**Recommendation:**`, `**Risk:**`, `**Impact:**` — one short sentence each. Parse them **leniently** when creating the Approval: store found sections in the approval's payload; if any are missing (old data, adversarial profiles), fall back gracefully — the UI renders whatever exists plus the raw audit summary. The trailing Verdict line remains the ONLY hard parse contract; never let section parsing failure block the pipeline. Update MockProvider's reviewer output to emit the sections.

**1c. Situation Report (§3.2).** `GET /api/projects/{id}/situation` returns 1–2 sentences of PM-voiced prose about the current state (pending decisions, missions in flight, last notable event), generated via ProviderGateway with a cheap deterministic fallback (mock mode: templated from live counts). Cache for a few minutes or regenerate on material events — your call, log it. This is NOT the Daily Report; it's a glanceable one-liner.

**1d. Hygiene.** Profile PUT validates `model_ref` against model_registry known models (reject unknown with a clear error) — closes the Sprint 4.5 review note.

Commit: `feat(core): internal template, structured decisions, situation report`

## Phase 2 — Status Vocabulary (§1)

One source of truth for external status words, shared by both sides: backend exposes internal→UI mapping keys in contracts (regenerate TS), frontend gets a `StatusWord` component + token map used EVERYWHERE a status renders (cards, badges, kanban columns, filters). Copy per §1's table — notably `Needs your decision` (never "Waiting Approval"), `Blocked — see why`, `Failed — see report`. Grep the dashboard for stray internal-state strings and replace them all.

Commit: `feat(ux): unified status vocabulary`

## Phase 3 — Decisions Page (§3.6)

New route `/company/[id]/decisions`, sidebar item. Two tabs: **Pending** and **History** (immutable, newest first). DecisionCard component with the fixed anatomy: Problem / Recommendation (with Reviewer avatar + name) / Risk / Impact, then Approve · Request changes (comment) · Reject. History cards additionally show the CEO's decision + comment and what happened after (mission completed / re-run / cancelled — derive from task state). Missing sections render gracefully (Phase 1b). This DecisionCard replaces the existing approval card on Headquarters too — one component, two placements.

Commit: `feat(dashboard): decisions page + DecisionCard anatomy`

## Phase 4 — Timeline Page (§3.5)

New route `/company/[id]/timeline`, sidebar item. Full-page live feed reusing the existing SSE plumbing: conversation events as meeting bubbles, system events as compact rows. Filter tabs: All / Meetings / Decisions / System. A subtle **CEO view ↔ Technical view** toggle: CEO view hides L3 mechanism rows (provider retries, model resolution, heartbeat-ish noise — define the hidden set as data, not scattered conditionals); Technical view shows everything. **Digest grouping:** 4+ consecutive minor system events collapse into one expandable row ("14 routine events"). Cursor pagination for history ("load earlier").

Commit: `feat(dashboard): timeline page with filters, CEO/technical toggle, digests`

## Phase 5 — Headquarters Rework + Companies + Nav (§3.2, §3.1)

- **Headquarters top-to-bottom:** (1) Decision strip hero — pending DecisionCards; when empty, the quiet line "Nothing needs your decision."; (2) PM Situation Report block (Phase 1c) with PM attribution + timestamp; (3) Vitals: Missions active · Employees working · Risks open · Payroll this month — each links to its page; (4) condensed live Timeline with "Open full Timeline".
- **CompanyCard upgrade (`/`):** status word, milestone progress "n/m Missions" + thin bar (NEVER a bare percentage — §8.2), Employee avatar stack with live-state dots, one line of latest activity, and a decision badge that visually outranks everything.
- **Sidebar order (§2):** Headquarters → Decisions → Missions → Employees → Timeline → Reports → Settings. Reports gets its own page/list if it's currently only a card.

Commit: `feat(dashboard): headquarters rework, company cards, nav`

## Phase 6 — Onboarding (§4, §6)

First-run path must reach a live Mission in under 3 minutes: empty `/` shows the founding invitation ("Found your first company", name + optional purpose, one button); post-founding, Employees introduce themselves in the Timeline (template-provided intro lines, emitted as conversation events at founding); empty Missions state offers one **starter Mission suggestion** (from the template's starters) creatable in one click. Every empty state across the app becomes an invitation to act, never a blank void (§5 EmptyState set).

Commit: `feat(dashboard): onboarding + empty states`

## Phase 7 — Verification & Doc Sync

Tests: template-driven founding identical to before; decision-section parsing (all present / some missing / none); situation endpoint (mock deterministic); status mapping completeness (every internal state has a word); model_ref validation. All 56 existing tests green (adjust only where the template refactor legitimately moved constants). `tsc --noEmit` + `next build` clean. Live E2E mock run: found fresh company → intros appear → starter mission → pipeline → DecisionCard shows 4 sections → approve from /decisions → History updated → Timeline toggle + digest verified → CompanyCard reflects state. Update CLAUDE.md (status; note "internal template" in layout), ARCHITECTURE.md (template file, situation endpoint, decisions/timeline pages), DECISIONS.md.

Commit: `chore(sprint4.7): tests, verification, doc sync`

---

## Out of scope

Template picker or any second template (§10.4: hidden means ABSENT), Workspace/diff views, Launch, auth, public website, notification channels, KO localization (English UI copy from the spec).

## Definition of Done

`make seed && make dev` → `/` shows upgraded CompanyCards → found a new company → watch Employees introduce themselves → create the suggested starter Mission → pipeline runs → Headquarters shows Situation Report + decision hero → open `/decisions`, see Problem/Recommendation/Risk/Impact, approve → History records it → `/timeline` filters + CEO/Technical toggle + digest grouping work live → no internal-state strings anywhere in the UI → all tests green → `PROGRESS.txt` 100% with honest timestamps.

---

## Appendix A — PROGRESS.txt checklist (create verbatim)

```
================================================
 COMMANDER — SPRINT PROGRESS
 Sprint: 4.7 — Headquarters UX
 Overall: 0/49 items · 0%
 Now working on: —
 Last update: (set on creation)
================================================

PHASE 1 — Backend Foundations                                  (0/10)
[ ] 1.1  software_company template data file
[ ] 1.2  Founding reads template (trio, profiles, intros)
[ ] 1.3  Workflow engine reads role order from template
[ ] 1.4  No hardcoded role-name branching outside template
[ ] 1.5  Reviewer contract: Problem/Recommendation/Risk/Impact sections
[ ] 1.6  Lenient section parser -> approval payload (Verdict still only hard contract)
[ ] 1.7  MockProvider reviewer emits sections
[ ] 1.8  GET /projects/{id}/situation (+ mock deterministic fallback)
[ ] 1.9  Profile PUT validates model_ref against registry
[ ] 1.10 Commit: feat(core)

PHASE 2 — Status Vocabulary                                    (0/4)
[ ] 2.1  Mapping in contracts + TS regen
[ ] 2.2  StatusWord component + token map
[ ] 2.3  Replace every status render site (grep-verified)
[ ] 2.4  Commit: feat(ux)

PHASE 3 — Decisions Page                                       (0/6)
[ ] 3.1  /decisions route + sidebar item
[ ] 3.2  DecisionCard: 4 sections + reviewer attribution + 3 actions
[ ] 3.3  Graceful rendering when sections missing
[ ] 3.4  History tab: CEO decision + comment + outcome
[ ] 3.5  Headquarters reuses the same DecisionCard
[ ] 3.6  Commit: feat(dashboard): decisions

PHASE 4 — Timeline Page                                        (0/6)
[ ] 4.1  /timeline route + sidebar item (SSE live)
[ ] 4.2  Filters: All / Meetings / Decisions / System
[ ] 4.3  CEO/Technical toggle (hidden set defined as data)
[ ] 4.4  Digest grouping (4+ minor system events collapse)
[ ] 4.5  Cursor pagination (load earlier)
[ ] 4.6  Commit: feat(dashboard): timeline

PHASE 5 — Headquarters + Companies + Nav                       (0/7)
[ ] 5.1  Decision strip hero (+ calm empty line)
[ ] 5.2  Situation Report block (PM attribution + timestamp)
[ ] 5.3  Vitals linked to their pages
[ ] 5.4  Condensed live feed + open-full link
[ ] 5.5  CompanyCard: status word, n/m milestones, avatar stack, activity, decision badge
[ ] 5.6  Sidebar reorder + Reports page/list
[ ] 5.7  Commit: feat(dashboard): headquarters

PHASE 6 — Onboarding                                           (0/6)
[ ] 6.1  Founding invitation empty state on /
[ ] 6.2  Employee intro events at founding (template intros)
[ ] 6.3  Starter Mission suggestion (one-click create)
[ ] 6.4  EmptyState pass across all pages
[ ] 6.5  Timed check: founding -> live mission < 3 min
[ ] 6.6  Commit: feat(dashboard): onboarding

PHASE 7 — Verification & Doc Sync                              (0/10)
[ ] 7.1  Tests: template founding parity
[ ] 7.2  Tests: section parsing (present/partial/none)
[ ] 7.3  Tests: situation endpoint (mock deterministic)
[ ] 7.4  Tests: status mapping completeness
[ ] 7.5  Tests: model_ref validation
[ ] 7.6  All pre-existing tests green
[ ] 7.7  tsc --noEmit + next build clean
[ ] 7.8  Live E2E per Definition of Done
[ ] 7.9  CLAUDE.md + ARCHITECTURE.md + DECISIONS.md sync
[ ] 7.10 Commit: chore(sprint4.7)
================================================
```