# Commander UI/UX Specification

Version: 2.0 (V1.1)
Scope: Product experience and information architecture. No implementation details, no code.
Status: Source of truth for all frontend work. Supersedes v1.1 (V1 spec).

> **Commander is not an AI chat application.**
> **Commander is software for operating an AI company.**
>
> Every experience decision reinforces this. When a design question is genuinely ambiguous, the tiebreaker is: *what would a real company do?*

**Reading guide.** §1–§6 define the V1.1 experience. §7 preserves the V1 surfaces that continue to exist. §8–§10 are cross-cutting discipline (copy, risks, gating). Items marked *[V1.1 — not built]* require an explicit sprint brief.

---

## 1. UX Philosophy

**The CEO's workspace is a conversation, not a dashboard.**
This is the central reversal in V1.1. In V1, entering a company presented a grid of panels and the CEO had to assemble a mental picture from them. In V1.1, entering a company presents **the PM**, who reports. The organization speaks first; the CEO responds. Dashboards exist, but they are peripheral instruments around a conversation, not the main event.

**CEO first, never developer first.** Every screen answers "what is happening in my company?" before "what changed in the system?" Every number has a sentence next to it, written by the company to its CEO.

**Employees, not chatbots.** Employees have names, avatars, roles, models, states, and voices. There is no "prompt box" as a primary surface — the CEO speaks to the PM, and the PM runs the company.

**Trust through visibility, not through claims.** Autonomy is acceptable only when observable, explainable, and reversible. Everything material appears in the Timeline; every agent action carries a reason; every consequential change routes through a CEO Decision; history is never deleted. The UI never simulates certainty — if the company doesn't know, it says so.

**Minimal surface, deep interior.** Benchmark: Render. Projects first. Avoid information overload. Complex capability lives behind Widgets and Sidebar pages, never crowded into the conversation.

**Honest numbers.** No invented precision. Progress is milestone-based and labeled as such — never a fabricated "72%". If a metric can't be computed honestly, show a status word instead.

### 1.1 Progressive disclosure — four levels

- **L0 — glance:** company card ("Developing · 2 Missions active · 1 decision waiting")
- **L1 — conversation:** the PM's report and the CEO's reply
- **L2 — instruments:** Widgets in the dock, Sidebar pages
- **L3 — mechanism:** diffs, raw events, model/config details, tool-call traces — opt-in only

Hiding rule: **hide the mechanism, never hide the fact.** "The Engineer hit an error and is retrying" is always shown; the retry's provider-level detail is L3.

### 1.2 Status vocabulary (external)

Internal states never reach the CEO's eyes. One source, reused by every card, badge, column, filter, and report.

| Internal | UI (EN) | UI (KO) |
|---|---|---|
| planning | Planning | 기획 중 |
| discussing | In discussion | 협의 중 |
| awaiting spec approval | Needs your decision | 결정 대기 |
| working / in_progress | Developing | 개발 중 |
| waiting_review | Reviewing | 검토 중 |
| waiting CEO decision | Needs your decision | 결정 대기 |
| blocked | Blocked — see why | 중단됨 |
| budget exhausted | Paused — resource limit | 예산 초과 |
| completed | Completed | 완료 |
| failed | Failed — see report | 실패 |

"Needs your decision," not "Waiting Approval" — the copy addresses the CEO directly.

---

## 2. Information Architecture

```
Pre-login
└── Sign in · Sign up                                    [V1.1 — Sprint 9]

Commander App
├── Projects (Overview)             /                    ← Render's "my services" applied to companies
├── Found a Company                 modal / first-run
└── Company                         /company/[id]
    │
    ├── ★ CEO Workspace             .                    ← DEFAULT LANDING. PM conversation + Widget Dock
    │
    ├── Missions                    /missions
    │   └── Mission detail          /missions/[id]
    ├── Employees                   /employees            ← includes Add Employee flow  [V1.1]
    │   └── Employee profile        /employees/[id]
    ├── Decisions                   /decisions
    ├── Timeline                    /timeline
    ├── Reports                     /reports
    ├── Workspace                   /workspace
    └── Company Settings            /settings
```

**Top bar** carries the company switcher (left) and the CEO account menu (right) — the Render pattern. **Sidebar** is thin and grouped; it is a set of deeper instruments, not the primary workspace.

**Entering a company always lands on the CEO Workspace.** Not Headquarters, not a mission list — the PM, mid-report.

**Rule: new capability arrives as a Widget or a Sidebar page.** Nothing new is attached to the conversation area. This keeps the center stable as the product grows.

---

## 3. The CEO Workspace — the core screen  *[V1.1 — Sprints 13–15]*

**Sprint 14 status:** the layout below (PM conversation as primary surface + Widget Dock) is the target for the end of this three-sprint span, not what Sprint 14 alone ships. Sprint 14 shipped the responsive Workspace *shell* at `/company/[id]` — a bounded set of summary cards (`PrimaryActionPanel`, `CurrentFocusCard`, `PendingAttentionList`, `PlanningSummaryCard`, `MissionSummaryCard`, `OrganizationSummaryCard`, `RecentActivityList`; see `docs/ARCHITECTURE.md` §8) driven by the same `next_action`/`WorkspaceSnapshot` contract this section describes — deliberately without a PM conversation surface or a customizable Widget Dock, both of which are Sprint 15 scope. The mapping from today's cards to tomorrow's Widgets is in `docs/ARCHITECTURE.md` §8.

```
┌──────────────────────────────────────────────────────────────────────┐
│  ▾ Acme AI                                    Search      ⊕  ⚙  (S)  │
├────────┬──────────────────────────────────┬──────────────────────────┤
│        │                                  │  Widget Dock         [+] │
│  Side  │      PM CONVERSATION             │  ┌────────────────────┐  │
│  bar   │      (primary surface)           │  │ Progress           │  │
│        │                                  │  │ 4 / 7 Missions     │  │
│  ·     │  ┌────────────────────────────┐  │  └────────────────────┘  │
│  ·     │  │ PM · 09:12                 │  │  ┌────────────────────┐  │
│  ·     │  │ Current Progress …         │  │  │ Pending Approvals  │  │
│  ·     │  │ Completed Work …           │  │  │ 1 waiting          │  │
│  ·     │  │ Current Blockers …         │  │  └────────────────────┘  │
│  ·     │  │ Estimated Completion …     │  │  ┌────────────────────┐  │
│  ·     │  │ Needs your decision …      │  │  │ Employees          │  │
│  ·     │  └────────────────────────────┘  │  │ ● ● ○ ○            │  │
│  ·     │                                  │  └────────────────────┘  │
│  ·     │  ┌────────────────────────────┐  │                          │
│  ·     │  │ CEO                        │  │                          │
│  ·     │  └────────────────────────────┘  │                          │
│        │  ┌──────────────────────────┐    │                          │
│        │  │ Message your PM…         │    │                          │
└────────┴──────────────────────────────────┴──────────────────────────┘
```

**The conversation is always the largest area on the screen.** That is a hard layout constraint, not a default.

### 3.1 Who the CEO can talk to

**Only the PM.** There is no UI through which the CEO messages an Engineer, the CTO, or the Reviewer — not disabled, *absent*. Other Employees are visible (Timeline, Employees page, Widgets) and audible (their work and words appear), but they communicate through events, and the PM speaks for the organization.

The Meeting transcript on a Mission remains readable — the CEO can watch any conversation. Reading is not the same as directing.

### 3.2 The PM Report

**The standalone CEO Brief / Situation Report block is removed.** A separate summary card competing with the PM's own voice is redundant and breaks the fiction. Instead the PM reports *in the conversation*, the way a real project manager does.

An opening report is posted when the CEO enters, and periodically as work advances. Its shape:

> **Current Progress** — where the project stands, in one or two sentences
> **Completed Work** — what closed since the CEO was last here
> **Current Blockers** — what is stuck, and why, in plain language
> **Estimated Completion** — honest, hedged when uncertain, or "can't estimate yet" — never fabricated
> **Decisions requiring your approval** — with a link to each Decision Card

This must read like a person reporting, not a generated status object. Headings may be softened into prose; what is fixed is that all five things are addressed and nothing material is omitted.

### 3.3 CEO replies

Natural language. Approve, ask, redirect, or set new direction. The PM interprets, and when interpretation requires technical judgment, the PM discusses it with the CTO before answering — visibly, in the Timeline. The CEO sees "PM is consulting the CTO" rather than an unexplained pause.

**The CEO's instruction may be vague.** "Build an ecommerce site" is a complete, valid input. Turning it into a specification is the organization's job, not the CEO's (§5.1).

---

## 4. The Widget Dock  *[V1.1 — Sprint 15]*

The dock is the CEO's instrument panel: glanceable state that would otherwise clutter the conversation.

- **Customizable.** `+` opens a widget catalog. Widgets can be added, removed, and reordered. Layout persists per CEO per company.
- **Only real widgets appear in the catalog.** A widget whose data does not yet exist is not listed, not greyed out, not "coming soon" (§10.2).
- **Every widget is a summary with a destination.** Tapping a widget opens the Sidebar page or detail view that owns that data. Widgets never become mini-apps.

Widget catalog (V1.1 target set — shipped progressively as their data becomes real):

| Widget | Shows | Depends on |
|---|---|---|
| Progress | milestone completion (n/m Missions) | V1 |
| Pending Approvals | decisions waiting on the CEO | V1 |
| Timeline | most recent activity, condensed | V1 |
| Employees | roster with live state dots | V1 |
| Decisions | recent decisions + outcomes | V1 |
| Costs | spend this month | V1 |
| Payroll | per-Employee spend | V1 |
| Token Usage | consumption against the resource limit | Sprint 9 |
| Reports | latest report + generate action | V1 |
| Risks | open risks from Reviewer findings | V1 (derived) |
| Repository Activity | recent commits and merges | V1 |
| Mission Tree | Project → Mission → Task progress | Sprint 19 |
| Architecture | current architecture decisions | Sprint 12 |
| Sprint | current sprint state | Sprint 18 |

---

## 5. Organization Experience

### 5.1 From instruction to specification  *[V1.1 — Sprint 12 ✅]*

```
CEO: "Build a shopping mall."
        │
   PM ⇄ CTO discuss (visible in the Timeline)
        │
   PM: "Before we start, I need a few things from you —
        who are the target customers? Is an admin page needed?
        Which payment methods? Which login methods? Expected scale?"
        │
   CEO answers (or says "you decide")
        │
   Project Specification → CEO Decision → Kick-off
```

Requirement Discovery is a **feature of the organization, not a form.** The PM asks because a real PM would ask, and asks only what actually matters — the questions themselves are produced by the PM/CTO discussion, not from a fixed checklist.

The Specification presented to the CEO is readable in under two minutes: Goal · Target User · Core Features · Technical Constraints · Acceptance Criteria · Risks. Engineering does not begin before approval.

**As built:** the CEO Workspace / PM conversation surface this section assumes doesn't exist yet (Sprints 13–15), so Sprint 12 shipped the Specification lifecycle as its own **Specifications** Sidebar page (Rule #17) rather than inside a Timeline/conversation view — a list (`/company/[id]/specifications`) with a "Start Planning" action that's disabled with inline guidance when no CTO is hired, and a detail page per Specification showing the PM↔CTO turn transcript, clarification Q&A, version history, and the approve/revision/reject/cancel actions. When the PM conversation surface ships, this page's content is the natural candidate to surface *through* that conversation instead of only next to it; that migration is deferred to whichever of Sprints 13–15 implements it, not assumed here.

### 5.2 Decisions reach the CEO only when they matter  *[V1.1 — not yet scheduled]*

The PM classifies. Minor decisions the PM makes alone; Major ones the PM makes with the CTO; only Critical ones become CEO Decisions. Both lower tiers remain fully visible in the Timeline — the CEO can always see what was decided without them, which is what makes the delegation trustworthy rather than opaque.

If everything asks, nothing matters. If nothing asks, the CEO isn't a CEO.

### 5.3 The Decision Card — unchanged anatomy

Still the product's most important component:

> **Problem** — one sentence, plain language
> **Recommendation** — what the company proposes, and who proposes it (avatar + name)
> **Risk** — what could go wrong, stated honestly
> **Impact** — what approving changes (scope, cost, time)
> Actions: **Approve** · **Request changes** (with comment) · **Reject**

V1.1 adds one variant: the **Specification approval** card, whose body is the specification summary rather than a single problem statement.

### 5.4 Employees  *[Sprint 10 ✅ grouped-by-category display; Sprint 11 ✅ CTO, hiring, per-Employee configuration]*

Sprint 10 shipped the grouping-by-`Role.category` behavior below for the
current PM/Engineer/Reviewer roster (`Leadership`/`Engineering` section
headings, a section hidden entirely when it holds no hired Employee — §10.4).

Sprint 11 shipped a second Leadership Role (CTO, vacant/hireable rather
than auto-seeded — see `docs/DECISIONS.md` #178), the **Hire Employee**
action, and per-Employee skill-template editing. The Backend/Frontend
Engineer split shown in the illustrative diagram below is **not yet
shipped** — Sprint 11 has one `engineer` worker Role, and multiple
Employees can already be hired into it. The split is deferred to a later
sprint as data (a template change, not an engine change).

**Roles are positions; Employees are people.** The Employees page shows the org, grouped by role:

```
Leadership              (permanent, exactly one each)
  PM        · Jun    · Claude Sonnet
  CTO       · Mina   · Claude Opus     (or: vacant — hireable)
  Reviewer  · Tae    · Claude Sonnet

Engineering             (unlimited)
  Engineer
    · Kim   · Claude Sonnet · Speed-Focused
    · Lee   · Claude Sonnet · Research-Focused

                                        [ + Hire Employee ]
```

**Hiring entry point:** a single **"+ Hire Employee"** button (`components/NewEmployeeForm.tsx`) above the grouped roster, matching the existing inline expand/collapse pattern used by "+ New Mission." Disabled (not hidden) when every Role is a filled singleton — i.e. there is nothing left to hire.

**Hire form fields:**
- **Role** — a `<select>` populated from `GET /api/projects/{id}/roles`. Every Role always appears, including occupied singleton Roles; an occupied singleton Role's `<option>` is `disabled` and its label is suffixed `"(already hired)"` rather than removed from the list — the CEO can see the position is filled, not wonder why it vanished.
- **Employee name** — free-text, required, trimmed before submit. Submit stays disabled until non-empty.
- **Model** — a `<select>` populated from `GET /api/projects/{id}/models`, scoped to the selected Role's registry role (derived from `RoleResponse.model_ref`, never a hardcoded Role→model map). Defaults to "Use company default."
- **Skill template** — a `<select>` populated from `GET /api/projects/{id}/skill-templates` (key/title/description only). Defaults to the server-side default when left unset.

**Singleton / occupied state:** the effective Role selection auto-advances past occupied singletons (`hireableRoles[0]`) so the CEO never lands on a disabled option by default; attempting to submit against an occupied singleton is also rejected client-side before the request is sent, and would be rejected server-side (409) regardless.

**Multiple-Employee display:** worker Roles render one card per hired Employee, unbounded; hiring a second, third, … Employee into the same worker Role never disables the Role option.

**Editing flow:** the existing Employee profile page (`EmployeeProfile.tsx`) gained a Skill Template `<select>`, wired to `PUT /api/agents/{id}/profile`'s `skill_template_key` field, alongside the model selector that already existed. Saving shows the same "Saved." confirmation used by the rest of the page. Editing one Employee never changes another Employee's configuration or the Role itself.

**Loading / success / error / empty states:** the Hire button reads "Hiring…" and is disabled while the mutation is pending (no duplicate submission). On success the form collapses and the roster + Timeline refetch. On failure — invalid Role/model/skill, a filled singleton (409), or a network error — the existing global toast/error system surfaces the message; no partial Employee ever appears in the roster. The page's pre-existing loading/empty states are unchanged.

**Add Employee flow (summary):** select Role → select AI model → select skill template → name → create. The Role is a position with fixed behavior; the Employee is a worker with an identity, a model, and a skill template. The UI must make that distinction legible — a CEO should understand that hiring a second Engineer on a different model/skill template is a staffing choice, not a configuration change.

Leadership roles cannot be removed or duplicated; the UI never offers the action.

Future roles (Designer, QA, DevOps, Security, ML Engineer, Data Analyst, Technical Writer, the Backend/Frontend Engineer split, …) appear in the role list only when the template actually defines them — no dashboard code change required.

**Browser verification status:** UNVERIFIED. No browser automation tool was available in this environment for Sprint 10 or Sprint 11 (re-confirmed at Sprint 11 Phase 0, Phase 4, and Phase 5). Typecheck and production build are green; the hiring flow above is verified at the API/integration level (`tests/test_hiring.py::test_full_hiring_flow_end_to_end`) but the actual rendered UI, click-through, and keyboard/focus behavior have not been observed in a browser.

---

## 6. First Session → Steady State

1. **Sign up** → **Projects** (empty) → "Found your first company"
2. **Found** — name + optional "what should it build". Leadership and starting Employees appear and introduce themselves.
3. **Land in the CEO Workspace** — the PM opens with a report and a question.
4. **Give a vague instruction** — the PM and CTO discuss it, ask what's missing, and return a specification.
5. **Approve** — the first Decision Card. The role reversal lands: the company asks *your* permission.
6. **Watch** — work proceeds; the dock updates; the Timeline fills.
7. **Leave and return** — the PM's first message summarizes the absence.
8. **Steady state** — read the PM's report, clear decisions, set direction, occasionally open a Widget or Sidebar page. Sessions get *shorter* as trust grows. That is success, not churn.

Onboarding must reach step 3 in under two minutes and step 5 in under five, with zero configuration — mock mode makes this possible and must never regress.

---

## 7. Sidebar Pages (V1 surfaces, retained)

These already exist and continue to; most also project a Widget into the dock. One V1 surface is *not* on this list on purpose: **Headquarters is absorbed into the CEO Workspace**, not carried forward as its own Sidebar page. Its Decision strip becomes the Pending Approvals widget (plus the PM Report's decision section), its Situation Report becomes the PM Report itself, its four Vitals tiles become the Progress / Employees / Risks / Costs widgets, and its Timeline excerpt becomes the Timeline widget — see `docs/ARCHITECTURE.md` §8 for the full mapping.

- **Projects `/`** — Render's Overview applied to companies: name, status word, milestone bar, Employee avatar stack, latest activity line, decision badge. Empty state is the founding invitation.
- **Missions** — kanban (Backlog / Developing / Needs your decision / Done) + Mission detail: Meeting transcript, deliverable, decision history. Code missions render the **Change Summary Card** (summary → files → diff, strictly that order) with check results as plain verdict chips. The diff is never the landing view.
- **Employees** — §5.4.
- **Decisions** — Pending / History (immutable). History shows the decision, the CEO's comment, and what happened after.
- **Specifications** *[Sprint 12 ✅]* — §5.1. List + detail for the Project Specification lifecycle; "Start Planning" is disabled with inline guidance when no CTO is hired.
- **Timeline** — the company's collective memory and the trust engine. Conversation events as meeting bubbles, system events as compact rows, filters, CEO ↔ Technical toggle, digest grouping for consecutive minor events. The feed must never become a log file. V1.1 adds discussion turns, tool calls, and memory recalls to the Technical view.
- **Reports** — executive memo list + reader; readable in 60 seconds.
- **Workspace** — the company's real git-backed codebase: file tree, file viewer, merge history. Read-only.
- **Company Settings** — provider, write-only API key field, per-role model reassignment, execution sandbox toggle, resource limits.
- **`/company/[id]/overview`** *[Sprint 13 proof page, retired Sprint 14]* — the CEO Workspace shell (§3, this sprint's interim shape) now lives at the company landing route itself. This URL is kept only as a `redirect()` to `/company/[id]` so pre-Sprint-14 deep links still resolve; it is not a page a CEO is ever routed to.

---

## 8. Component Inventory

★ = carries the product's identity.

- ★ **PMConversation** — the primary surface: report messages, CEO composer, live streaming replies *[V1.1]*
- ★ **PMReport** — the five-part report rendered as a message, not a card *[V1.1]*
- ★ **WidgetDock / WidgetCard / WidgetCatalog** — add, remove, reorder *[V1.1]*
- ★ **DecisionCard** — Problem / Recommendation / Risk / Impact + three actions (+ Specification variant)
- ★ **TimelineFeed** — MeetingBubble + SystemRow + DigestRow
- ★ **ChangeSummaryCard** — summary → files → diff
- **SpecificationView** — readable Project Specification *[V1.1]*
- **EmployeeRoster / AddEmployeeFlow / RoleGroup** — org as org *[V1.1]*
- **EmployeeCard / StatusBadge / LiveDot** — presence and state
- **CompanyCard** — status word, milestone bar, avatar stack, decision badge
- **MissionCard / MissionBoard**
- **MeetingTranscript** — readable, not writable by the CEO *[V1.1 change]*
- **ReportCard / ReportReader**
- **StatusWord** — the single source of external status vocabulary
- **ProgressMilestones** — honest progress, never bare percentages
- **EmptyState** set — every empty screen is an invitation to act
- **TechnicalDisclosure** — the uniform "show technical details" affordance for all L3 content
- **AuthForms** — sign in / sign up *[V1.1 — Sprint 9, minimal; styled properly in Sprint 14]*

---

## 9. Copy Discipline

Every string is either **company voice** (the PM reporting, an Employee speaking, a report) or **interface voice** (buttons, labels, empty states). Mixing them breaks the fiction.

Generic components use organization language ("work", "deliverable", "team"); software-specific words live only in template-owned content. This costs nothing now and prevents a full copy audit when a second template eventually ships.

Both locales (EN / KO) share one vocabulary table (§1.2). Never hardcode a status string.

---

## 10. Risks & Standing Rules

1. **Theater vs. truth.** The company metaphor must never fabricate. An Employee "thinking" animation with no real work behind it poisons trust permanently. Every visible state maps to a real system state; delight comes from real events rendered warmly.
2. **Hidden means absent.** No "coming soon" tabs, no disabled menu items, no teaser widgets, no template picker with one option. A focused product that hints at an unfinished bigger one feels smaller, not bigger.
3. **Fake precision.** Ship milestone progress and status words. Introduce percentages only when a real estimation model exists.
4. **Conversation bloat.** The PM conversation is the center precisely because it is uncluttered. Rule #17 (new capability → Widget or Sidebar page) is load-bearing, not stylistic.
5. **Decision fatigue vs. rubber-stamping.** Delegation is only trustworthy when the CEO can see what was decided without them. Lower-tier decisions must remain fully visible in the Timeline.
6. **Timeline noise.** Volume grows faster than reading time. Digest grouping and the CEO/Technical toggle are load-bearing.
7. **Audience tension.** Early adopters are developers; the CEO framing could feel like hiding *their* details. The Technical toggle and full L3 reachability are the bridge — CEO-first defaults, developer-complete depths.
8. **Widget sprawl.** A dock with twenty widgets is a dashboard again. Ship the catalog with restraint and let the CEO opt in.

---

*This document contains no colors, spacing, or component code. Visual language continues from the existing dashboard identity — dark, violet accent, Render-inspired calm — unless a dedicated brand pass supersedes it. The Render benchmark governs structure and restraint, not palette.*
