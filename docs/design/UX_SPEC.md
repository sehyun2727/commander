# Commander UI/UX Specification

Version: 1.1 (adds §10 Future Expansion Strategy)
Author role: CPO / Senior SaaS Product Designer / UX Architect
Status: Proposed — awaiting CEO approval
Scope: Product experience and information architecture. No implementation details, no code.

---

## 0. Product Analysis (answers before design)

### Q1. What should a CEO see immediately after login?

In priority order: **(1) What needs my decision, (2) What is moving, (3) What just happened.**

A CEO's first question is never "what's the data" — it's "does anything need me?" So the first screen leads with pending CEO Decisions, then company health at a glance, then the freshest activity. Everything else is one click deeper.

### Q2. What should be hidden?

By default: raw event type names, state-machine states, model API identifiers, token counts, stack traces, diffs, retry mechanics. These exist and remain accessible (trust requires inspectability) but they live behind a deliberate "show technical details" action. The hiding rule: **hide the mechanism, never hide the fact.** "The Engineer hit an error and is retrying" is always shown; `provider_gateway 429 backoff attempt 2/3` is disclosure level 3.

### Q3. What makes Commander different from Cursor / Claude Code / Copilot?

Those are **tools you drive**: developer-in-the-loop, code-first, session-based — when you stop typing, everything stops, and the artifact you review is code. Commander is an **organization you govern**: outcome-first, decision-in-the-loop, and continuous — employees keep working while you're away, and what you review are reports, recommendations, and decisions. The unit of interaction is not a prompt but a Mission; the unit of output is not a diff but an accountable result with an explanation. Nobody using Cursor asks "what happened while I was gone?" That question is Commander's entire product.

### Q4. What creates the "wow moment"?

Four, in the order a new user meets them:

1. **Founding** — you name a company and three Employees appear with names, roles, and personalities, and introduce themselves in the Timeline. The org exists before any work does.
2. **The first Mission run** — you assign a Mission and *watch* the PM plan, the Engineer build, the Reviewer audit — live, in conversation, without you. This is the moment "AI tool" becomes "AI company."
3. **Being asked** — the Reviewer escalates a decision to you with a recommendation and a risk. The product asks *your* permission. Role reversal is the emotional core.
4. **The report** — you come back later and read "while you were away: 2 Missions completed, 1 decision pending, payroll ₩1,400." Absence produced results.

Design consequence: onboarding must reach moment 2 within ~3 minutes of first login, with zero configuration (mock mode makes this possible).

### Q5. MVP scope? Q6. Future expansion?

See §8 and §9. Summary: MVP is the CEO loop (found → assign → watch → decide → report) made trustworthy and legible. Expansion is depth of the company (real workspaces, execution, launches, org structure).

---

## 1. Product UX Philosophy

**CEO First.** Every screen answers "what is happening in my company?" before "what changed in the system?" Every number has a sentence next to it; every sentence is written by the company to its CEO, in executive language.

**Employees, not chatbots.** Agents have names, faces (avatar identity), roles, states, and voices. They speak in the Timeline like colleagues, not in a chat input-output pane. There is no "prompt box" as a primary surface; the CEO gives work by creating Missions and speaks with Employees in Meetings.

**Trust through visibility, not through claims.** Autonomy is only acceptable when it is observable, explainable, reversible. Hence: everything material appears in the Timeline; every agent action carries a reason; every consequential change routes through a CEO Decision; history is never deleted. The UI never simulates certainty — if the company doesn't know, it says so.

**Progressive disclosure in three levels.**
- L0 — glance: company card ("Developing · 2 Missions active · 1 decision waiting")
- L1 — situation: Headquarters (report sentences, vitals, live feed)
- L2 — domain: Missions / Employees / Timeline / Decisions pages
- L3 — mechanism: diffs, raw events, model/config details, opt-in only

**Honest numbers.** No invented precision. Progress is milestone-based (Missions completed vs. planned), labeled as such — never a fake "72%" derived from nothing. If a metric can't be computed honestly, show a status word instead.

### Status vocabulary (external)

Internal states never reach the CEO's eyes. Mapping (UI copy in both locales):

| Internal | UI (EN) | UI (KO) |
|---|---|---|
| planning | Planning | 기획 중 |
| working / in_progress | Developing | 개발 중 |
| waiting_review (agent review) | Reviewing | 검토 중 |
| waiting CEO decision | Needs your decision | 결정 대기 |
| blocked | Blocked — see why | 중단됨 |
| completed | Completed | 완료 |
| failed | Failed — see report | 실패 |

"Needs your decision" (not "Waiting Approval") — the copy addresses the CEO directly. This vocabulary is a design token: one source, reused everywhere (cards, badges, filters, reports).

---

## 2. Information Architecture

```
Public website (pre-login)                     [Phase E]
└── Landing · Product · (Docs) · Sign in

Commander App
├── My Companies                    /                     [exists — upgrade]
├── Found a Company                 modal / first-run
└── Company (CEO context)           /company/[id]
    ├── Headquarters (Overview)     .                     [exists — upgrade]
    ├── Missions                    /missions             [exists]
    │   └── Mission detail          /missions/[id]        [exists — upgrade]
    ├── Employees                   /employees            [exists]
    │   └── Employee profile        /employees/[id]       [new]
    ├── Timeline                    /timeline             [new page, feed exists]
    ├── Decisions                   /decisions            [new — archive + pending]
    ├── Reports                     /reports              [Sprint 4]
    ├── Workspace                   /workspace            [Phase D]
    └── Company Settings            /settings             [exists — upgrade]
```

Navigation: left sidebar within a company (CEO context); top bar carries the company switcher and the CEO identity. Entering a company is a context switch — the moment the user "becomes CEO of this company." The sidebar order mirrors CEO priority: Headquarters → Decisions → Missions → Employees → Timeline → Reports → Workspace → Settings.

---

## 3. Page Hierarchy & Key Screens

### 3.1 My Companies `/`

Render's "my services" philosophy applied to organizations. A grid of Company Cards; the page's single job is *"which of my companies needs me?"*

Company Card contents: company name + avatar mark · status word (vocabulary above) · milestone progress ("4 / 6 Missions" + thin bar) · Employee avatar stack with live-state dots · one line of latest activity ("Engineer completed the auth module") · a decision badge ("1 decision waiting") that visually outranks everything else on the card.

Empty state = the founding moment: "Found your first company." One field (name), one optional field (what it should build), one button. No configuration.

### 3.2 Headquarters `/company/[id]` — the core screen

Layout concept (top to bottom):

1. **Decision strip (hero).** Pending CEO Decisions as cards. If none: a quiet single line — "Nothing needs your decision." (calm is a feature, not emptiness).
2. **PM Situation Report.** One or two sentences of prose, generated, timestamped: "Payment work is paused waiting for your database decision. Two Missions are developing normally." This is the "CEO summary" — language before numbers.
3. **Vitals.** Four compact figures: Missions active · Employees working now · Risks open · Payroll this month. Each links to its domain page.
4. **Live Timeline (condensed).** The most recent activity streaming in, mixed feed (see 3.5), with "Open full Timeline."

### 3.3 Missions `/missions` + detail

Kanban: Backlog / Developing / Needs your decision / Done. Mission detail is a story, not a form: header (status, assignee avatars, cost so far), then the **Meeting transcript** (the conversation that produced the work), then the **deliverable** (summary card first — see 3.7), then the decision history for this Mission. Dependencies and blockers appear as labeled chips; a blocked Mission always states *why* in a sentence.

### 3.4 Employees `/employees` + profile

Grid of Employee Cards: avatar, name, role, live state badge, current Mission, one-line style ("Careful senior developer"). Clicking opens the **Employee profile** (new): role & responsibility statement · current model (shown as a plain name — "Claude Sonnet", never an API string) · personality & working style (from the Agent Profile system, editable when that ships) · performance history (Missions completed, audit outcomes, payroll) · "Start a Meeting" action. The profile is where "this is a colleague" solidifies.

### 3.5 Timeline `/timeline`

The company's collective memory and the trust engine. Full-page feed with two render modes in one stream: **conversation events** as meeting bubbles (avatar, name, role, text) and **system events** as compact single-line rows. Filters: All / Meetings / Decisions / System. A subtle "CEO view ↔ Technical view" toggle controls whether L3 detail rows (retries, provider events) appear. As volume grows, consecutive minor system events group into a collapsible digest row ("14 routine events") — the feed must never become a log file.

### 3.6 Decisions `/decisions`

The CEO's desk. Two tabs: **Pending** and **History** (immutable). Every Decision Card has a fixed anatomy — this is the product's most important component:

> **Problem** — one sentence, plain language
> **Recommendation** — what the company proposes, and who proposes it (Reviewer avatar + name)
> **Risk** — what could go wrong, stated honestly
> **Impact** — what approving changes (scope, cost, time)
> Actions: **Approve** · **Request changes** (with comment) · **Reject**

Only material decisions arrive here (architecture, external services, security, spend thresholds, destructive changes). Routine work never asks. History shows the decision, the CEO's comment, and what happened after — decisions have consequences, and the archive proves the system respects them.

### 3.7 Workspace `/workspace` — code without code-first  [Phase D]

The doc's principle, made concrete: **summary → files → diff**, strictly in that order.

Default view per change-set: a **Change Summary Card** — "Engineer modified 12 files. Added the authentication system. Potential risk: token expiration handling." plus test results as a plain verdict ("All 34 checks passed"). Expansion level 1: file list with per-file one-liners. Expansion level 2: full diff viewer. The diff is never the landing view, and nothing in L1/L2 requires reading code to make a decision — the Decision Card must carry everything material.

### 3.8 Reports `/reports`  [Sprint 4]

Daily Report list + reader. Executive memo format: headline, what moved, decisions made/pending, failures with causes, payroll. Written to be read in 60 seconds.

### 3.9 Public website  [Phase E]

Landing narrative, in order: **Hero** — "Become the CEO of an AI software company." One sentence on why this is not a coding assistant: your company works while you decide. A live-looking product frame (real Timeline animation, not screenshots of code). Then five sections matching the product's trust ladder: (1) The AI Company — found one in a minute; (2) Your Employees — roles, personalities, models; (3) How work happens — Mission → plan → build → audit; (4) The CEO experience — Headquarters, reports, one place to decide; (5) Trust & control — everything visible, every decision yours, full history. Close with the founding CTA. The page sells governance and delegation, never "code faster."

---

## 4. User Journey (first session → steady state)

1. **Land** → understand "I can run an AI company" → sign in
2. **Found** — name the company; 3 Employees appear and introduce themselves in the Timeline (wow 1)
3. **First Mission** — guided suggestion ("Try asking your team to build a landing page"); CEO assigns
4. **Watch** — live Meeting: PM plans → Engineer builds → Reviewer audits (wow 2)
5. **Decide** — first Decision Card arrives; CEO approves with full context (wow 3)
6. **Leave & return** — Daily Report summarizes what happened in absence (wow 4)
7. **Steady state** — CEO's loop becomes: read report → clear decisions → set new Missions → occasionally deep-dive an Employee or the Timeline. Sessions get *shorter* as trust grows — that is success, not churn.

---

## 5. Component List (design system inventory)

Priority-ordered; ★ = carries the product's identity.

- ★ **DecisionCard** — Problem / Recommendation / Risk / Impact + three actions
- ★ **TimelineFeed** — MeetingBubble (conversation) + SystemRow (compact) + DigestRow (grouped)
- ★ **EmployeeCard / EmployeeStatusBadge / LiveDot** — presence and state
- ★ **ChangeSummaryCard** — summary→files→diff progressive disclosure [Phase D]
- **CompanyCard** — status word, milestone bar, avatar stack, decision badge
- **SituationReport** — generated prose block with timestamp and PM attribution
- **VitalsStrip** — four linked figures
- **MissionCard / MissionBoard** — kanban with "Needs your decision" column
- **MeetingTranscript / MeetingComposer** — conversation view + CEO message input
- **ReportCard / ReportReader** — executive memo
- **StatusWord** — the single source of external status vocabulary
- **ProgressMilestones** — honest progress (n/m Missions), never bare percentages
- **EmptyState** set — every empty screen is an invitation to act (found, assign, decide)
- **TechnicalDisclosure** — the uniform "show technical details" affordance for all L3 content

---

## 6. MVP Scope (what "done" means for the experience)

The MVP is the complete CEO loop, legible and trustworthy, in mock or real mode:

My Companies with upgraded cards · Headquarters with Decision strip + Situation Report + vitals + live feed · Missions kanban + Mission detail with transcript and deliverable summary · Employees grid + basic profile · full Timeline page with filters and CEO/Technical toggle · Decisions page (pending + history) with the full DecisionCard anatomy · Reports (Sprint 4) · Settings. Status vocabulary applied everywhere. Onboarding path that reaches the first live Mission in under 3 minutes.

Explicitly **not** MVP: public website, Workspace/diff views, execution, Launch, multi-member orgs, CTO Agent, notification channels (email/Slack), mobile-dedicated layouts (responsive is enough).

---

## 7. Future Roadmap (experience layer)

- **Phase D (Workspace & Sandbox):** ChangeSummaryCard, file/diff disclosure, test verdicts in Audits; Risks become a first-class object (a Risk register fed by Reviewer findings)
- **Phase E (Launch & release):** Launch flow with mandatory Decision, launch history in Timeline; public website; onboarding polish
- **Beyond MVP:** CTO Agent (strategy recommendations in Headquarters) · org customization (departments, hiring new Employees) · personality editing UI (Agent Profile system) · notification digests to email/Slack · CEO command bar (natural-language "ask my company") · multi-company portfolio view with cross-company payroll

---

## 8. Risks & Recommendations

1. **Theater vs. truth.** The company metaphor must never *fabricate* — an Employee "thinking" animation with no real work behind it poisons trust permanently. Rule: every visible state maps to a real system state; delight comes from real events rendered warmly, never from invented ones.
2. **Fake precision.** "72% complete" cannot be computed honestly today. Ship milestone progress (n/m) and status words; introduce percentages only if a real estimation model exists. (This intentionally amends the example in the request document.)
3. **Timeline noise.** Event volume will grow faster than reading time. Digest grouping and the CEO/Technical toggle are not polish — they are load-bearing and belong in the first Timeline-page iteration.
4. **Decision fatigue.** If everything asks, nothing matters. Keep the materiality bar high (the request document's list is right); add per-company thresholds later (e.g., spend limits) rather than more approval types.
5. **Audience tension.** Early adopters are developers; the CEO framing could feel like hiding *their* details. The Technical toggle and full inspectability (L3 always reachable) are the bridge — CEO-first defaults, developer-complete depths.
6. **Two-sided copy discipline.** Every string in the app is either company-voice (reports, employees speaking) or interface-voice (buttons, labels). Mixing them breaks the fiction. Maintain a copy guide alongside the terminology table.

---

## 9. Adoption Plan (where this spec lands in the sprint flow)

| Spec element | Applies to |
|---|---|
| Status vocabulary, DecisionCard anatomy, SituationReport, Decisions page, Timeline page + toggle, Employee profile, CompanyCard upgrade, onboarding path | **Sprint 4.7 — "Headquarters UX"** (new UI-focused sprint after Real Intelligence; pairs naturally with Sprint 4.5 Employee Profiles) |
| Reports reader | Sprint 4 (already specced; align copy with §3.8) |
| Personality display/editing in Employee profile | Sprint 4.5 (Agent Profiles) |
| ChangeSummaryCard, Workspace page, Risk register | Sprint 5–6 briefs (Phase D) — this spec's §3.7 is the UX requirement for Workspace |
| Public website | Sprint 8 (Phase E) — §3.9 is the content architecture |
| Template-data founding refactor (§10.6, internal only) | Sprint 4.7 — backend item, zero UI change |
| This document | `docs/design/UX_SPEC.md` — source of truth; all future frontend briefs reference it; CLAUDE.md gains a pointer |

---

## 10. Future Expansion Strategy — from AI Software Company to AI Organization OS

MVP scope is unchanged by this section. Everything here is about making today's design *evolvable*, not about building any of it now.

### 10.1 How Commander evolves beyond software development

The honest audit: most of Commander is **already organization-agnostic**. Company, Employees, Missions, Meetings, Timeline, Decisions, Reports, Payroll, profiles, the event architecture, PromptBuilder's layering — none of these know they belong to a software company. Only four things do:

1. The **founding trio** (PM / Engineer / Reviewer) hardcoded at company creation
2. The **workflow shape** (plan → build → audit) hardcoded in the engine
3. The **deliverable type** (code/diffs, Phase D Workspace)
4. Scattered **copy** ("Developing", development-flavored strings)

Therefore the evolution path is not a redesign — it is the extraction of those four things into data. A future organization type is: a set of roles (with role contracts and default profiles), a workflow shape, a deliverable type, and a vocabulary. That tuple is a **Template**.

### 10.2 How Company Templates should work

A Template is a data document, not code:

```
Template
├── identity        name, description, icon
├── roles[]         role_key, title, default AgentProfile,
│                   role contract (incl. output contract like Verdict),
│                   audit criteria for this domain
├── workflow        ordered stages mapping roles to steps
│                   (plan → produce → review is one shape, not the shape)
├── deliverable     type key (code | document | design | video-script | …)
│                   → selects the summary/detail renderer
├── vocabulary      status-word overrides (a Research Lab "Experimenting",
│                   an Agency "Producing" — mapped onto the same internals)
└── starters        suggested first Missions for onboarding
```

Founding flow, future version: Found a Company → choose Template → the team appears and introduces itself — identical emotional beat to today, one added step. Custom Organization is just a template authored by the user (much later: shared/marketplace templates).

Two design consequences worth locking now: **the Reviewer role and the Decision loop are universal** — every template must define a reviewer with domain audit criteria, because trust-through-review is Commander's identity, not a software feature. And **role contracts stay immutable per template** (the PromptBuilder layering from Sprint 4.5 already enforces this), which is what keeps a Copywriter's output parseable just like an Engineer's Verdict.

### 10.3 How today's UI supports this — without showing it

- **Navigation is already generic.** Headquarters / Missions / Employees / Timeline / Decisions / Reports / Settings apply to any organization. Only **Workspace** is domain-specific: treat it as a *deliverable-driven* nav item (it appears because the template's deliverable type is code), not a permanent fixture.
- **Founding modal stays single-step** but is built as the first step of a wizard-shaped flow, so a template picker can slot in front later without relayout.
- **Roles render from data, never from constants.** Employee titles, avatars, style lines all come from the DB/profile — already true; keep it true. No component may ever branch on `role === "engineer"`; branch on template-provided keys.
- **Status words are tokens** (§1) — a vocabulary override is a data swap, zero component changes.
- **Mission deliverable area is a keyed renderer.** Today it renders one type (markdown summary). Keep that renderer behind a `deliverable_type` key even while only one key exists.
- **Copy discipline:** generic components use organization language ("work", "deliverable", "team"); software words live only in template-owned content. This costs nothing now and prevents a full copy audit later.

### 10.4 What stays hidden until later versions

Template picker, custom organization builder, role library, non-software templates, template sharing/marketplace, multi-workflow shapes. Hidden means **absent** — no "coming soon" tabs, no disabled menu items, no teaser cards. A focused MVP that hints at a bigger unfinished product feels smaller, not bigger.

### 10.5 Risks of expanding too early

1. **The verifiability cliff.** Software is the *easiest* domain to build trust in: outputs have objective audits (tests pass, diffs review). Marketing copy and research have no such ground truth — a Reviewer's verdict becomes an opinion. Each new template needs real domain audit criteria, or the Decision loop (the product's core) degrades into theater. This is the single strongest reason to expand late.
2. **The prompt-pack trap.** A template that only swaps titles and personas produces five orgs with identical shallow output. Real differentiation requires deliverable types + audit criteria + workflow shapes per domain — genuine content and engineering work per template, not configuration.
3. **Wedge dilution.** "AI dev company" is a sharp, sellable story; "OS for any AI organization" is a vision statement. Marketing the vision before the wedge wins means competing with everyone while excelling at nothing.
4. **Surface explosion.** Every template multiplies the testing matrix, mock-provider content, onboarding paths, and support burden. MVP economics assume one path polished deeply.
5. **Sunk-cost tension with Phase D.** Workspace/Sandbox investment is software-specific. That's fine — it's the wedge — but plan it as *the code deliverable module*, not as Commander's spine, so generalizing later doesn't mean unwinding it.

### 10.6 Recommendations — focused MVP, scalable bones

1. **Implement the MVP as a template, invisibly.** Move the founding trio, workflow order, role contracts, and default profiles into a single internal `software_company` template data file. One template, no picker, zero UI change — but "Software Company can become Organization Template" then requires adding files, not redesigning systems. (Small backend refactor; slotted into Sprint 4.7.)
2. **Gate expansion on wedge quality, not ambition.** Add template #2 only after the software company sustains real usage quality (missions completed without babysitting, decisions trusted, retention). The vision is the reward for winning the wedge, not a substitute.
3. **Choose the second template for verifiability.** When the time comes, pick an adjacent domain whose outputs can still be audited semi-objectively (e.g., technical documentation studio) before opinion-heavy domains (marketing, design).
4. **Spend now only where it's free.** Data-driven vocabulary, data-driven roles, keyed deliverable renderer, wizard-shaped founding: near-zero cost today. Defer everything with real cost (renderer plugin system, template authoring UI, audit-criteria frameworks) until template #2 is scheduled.
5. **Keep the external identity as the wedge.** Publicly: Commander is the AI software company OS. Internally (docs, schema names): "organization" is acceptable vocabulary. Rename the product story only when a second template ships.

---

*This document intentionally contains no colors, spacing, or component code. Visual language continues from the existing dashboard identity (dark, violet accent, Render-inspired calm) unless a dedicated brand pass supersedes it.*
