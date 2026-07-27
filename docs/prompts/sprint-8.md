# MISSION: Commander Sprint 8 — V1 Release

Read `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/design/UX_SPEC.md`, and `docs/DECISIONS.md` first — source of truth for terminology, architecture rules, and current state. All architecture rules and the `PROGRESS.txt` discipline apply. Work autonomously start to finish; do NOT pause for confirmation between phases or items; log every judgment call in `docs/DECISIONS.md` under a new "Sprint 8" section. Commit AND PUSH per phase; a sprint is not complete until the remote HEAD matches the final commit — verify at the end.

Prerequisite: Sprint 7 merged (remote HEAD `ff4f648`), 157 passed / 4 skipped, Postgres + Alembic + health checks live.

---

## Framing: this sprint ships Commander V1

This is the final V1 sprint. When it's done, V1 is released. V1's promise is precise and must not drift: **Commander lets one person act as CEO of an AI organization (PM / Engineer / Reviewer) that collaborates on missions, produces real code deliverables in a git workspace, runs sandboxed checks, and routes every consequential choice through the CEO — all observable on a Timeline, runnable against a real LLM.** V1 is NOT a tool that autonomously builds production software; that iterative-worker capability is V1.5 and stays out of scope.

Sprint 8 is **polish, coherence, and demonstrability** — not new capability. Every task below either (a) fixes a rough edge a first-time user or a portfolio reviewer would hit, (b) makes the existing experience read as intentional and finished, or (c) makes the product easy to run and show. If you find yourself building a new capability, stop — log it as a V1.5 candidate in DECISIONS.md and move on.

**Hard boundary — do NOT build (all V1.5 or later):** Agent Harness / iterative Engineer loop, agent tools (`read_file`/`run_checks`/etc.), CTO agent, PM structured Specification, Project Memory, requirement-change flow, EngineerWorker interface, ClaudeCodeWorker, multi-user/auth, hosted cloud deployment, real "Launch to production" infrastructure. The Engineer stays a single-shot generator.

---

## Context you need (verified against current code)

- **The dashboard is functionally complete**: 10 routes render real content via ~19 components (Headquarters, Missions, Mission detail, Employees + profile, Decisions, Timeline, Workspace, Reports, Company Settings, company list). This sprint refines what exists; it does not add pages unless a gap below requires one.
- **Mock code output is a fixed 2-file static landing page** (`index.html` + `style.css`) that interpolates the mission title/description and changes accent color on re-runs. It's fine for pipeline demos but it's obviously templated, and the same shape regardless of what's asked. This is the main "demo honesty" rough edge (see Phase 2). Do NOT try to make mock genuinely intelligent — that's impossible without a model — but DO make it clearly, honestly a simulation and less likely to mislead a viewer into thinking it's real generation.
- **The real V1 demo runs against Anthropic** (`COMMANDER_PROVIDER=anthropic`). The verify-llm path exists from Sprint 7. The portfolio story depends on the real-mode run looking coherent end to end.

---

## Design decisions (approved — do not re-litigate)

- **Two demo modes, both first-class**: mock (zero-key, deterministic, for "watch the organization work" walkthroughs) and real (Anthropic, for "it actually generates" moments). The README walkthrough and the in-app onboarding must make clear which is which, so a viewer is never misled about what they're seeing.
- **Mock honesty over mock cleverness**: mock deliverables should carry a subtle, consistent signal that they're simulated (e.g. the Change Summary wording already hints "placeholder"; keep and slightly strengthen that), and mock mode should be labeled in the UI (a small, calm "Simulation mode" indicator — not alarming, just honest). Never fabricate check results, costs, or activity that didn't happen.
- **No visual redesign.** Keep the existing dark/violet Render-style identity and all UX_SPEC §3 structures. Polish means: consistent spacing/empty-states/loading-states/error-states, fixing anything that looks unfinished, and closing copy inconsistencies — NOT restyling.
- **Packaging target = "clone and run in minutes on a fresh machine with Docker."** Not an installer, not a hosted service. A newcomer follows the README and reaches a live company. `make` is the single entry point.
- **Accessibility & correctness basics only** (keyboard focus, alt/aria on interactive controls, no color-only status) — not a full audit.

---

## Phase 0 — Fresh-machine dry run & gap list (do first)

Simulate a brand-new user on a clean checkout to find what's actually broken/rough, rather than guessing:
- From a fresh clone: follow the README exactly. Note every friction point (a missing step, an unclear command, a confusing error, a slow/blocking moment).
- Boot in mock mode AND (if `ANTHROPIC_API_KEY` is available) real mode. Click through all 10 pages. Record every rough edge: broken/empty states, inconsistent copy, missing loading indicators, ungraceful errors, terminology leaks (internal terms in UI), dead ends.
- Write the findings as a checklist into `PROGRESS.txt` Phase 1–4 as `+` discovered items where they fit, and into `docs/DECISIONS.md`.
- Create `PROGRESS.txt` from Appendix A first (all `[ ]`), then backfill Phase 0.
- Commit+push: `chore(sprint8): fresh-machine audit + progress scaffold`

## Phase 1 — Experience coherence pass

Address the Phase 0 findings, plus these known targets:
- **State completeness**: every page has an intentional empty state (invitation to act, per UX_SPEC §5), a loading state (skeleton or calm spinner, no layout jump), and an error state (Commander-voiced, no raw errors). Audit all 10 routes.
- **Terminology sweep**: grep the dashboard for any internal-term leaks (project/task/agent/approval/repo/log) in user-facing strings; replace with Commander terms. Confirm StatusWord is used everywhere a status renders.
- **Copy consistency**: one voice across buttons/toasts/empty states (interface voice) vs. company/employee content (company voice). Fix mismatches.
- **First-run coherence**: founding → employees introduce themselves → suggested starter mission → live pipeline reads as one smooth story with no confusing gap.
- Commit+push: `feat(polish): experience coherence across all views`

## Phase 2 — Demo honesty & simulation labeling

- Add a calm, unobtrusive **"Simulation mode"** indicator visible when `COMMANDER_PROVIDER=mock` (e.g. a small pill in the top bar or company header). Tooltip/copy: brief, honest — this company is running on a simulated AI provider; connect a real provider in Company Settings for genuine output. Hidden in real mode.
- Strengthen the mock deliverable's honesty signal (Change Summary already says "placeholder"; ensure re-runs and audits also read as clearly simulated, never as verified real work).
- Company Settings: make the mock↔real switch and its consequences legible — what changes when you connect a key, where cost appears, that mock is free/fake and real incurs Payroll.
- Confirm nothing anywhere fabricates check results, costs, or Timeline activity that didn't occur (data-honesty is the product's core trust claim).
- Commit+push: `feat(polish): honest simulation labeling`

## Phase 3 — Packaging & one-command run

- **README as the front door** (portfolio-facing): a crisp what-it-is, a 60-second "what you'll see" summary, the exact prerequisites (Docker for Postgres + optional sandbox image, Node/pnpm, Python), and the shortest possible happy path. Ensure the documented commands work verbatim from a fresh clone.
- **`make` ergonomics**: confirm `make install`, `make dev`, `make seed`, `make verify-llm`, `make sandbox-image`, `make test` all work and are documented; add a `make demo` if it reduces the happy path to one obvious command (your call — log it). Every target prints a clear one-line description (a `make help` default target is welcome).
- **`.env.example` completeness**: every variable present with a safe default and a one-line comment; the real-provider path documented (where to put the key).
- **Sandbox optionality is clear**: with Docker + `make sandbox-image`, checks run; without, the app still works and says so. README states this plainly.
- **Clean the working tree**: resolve the two carried-over noise files from Sprint 7 (`.claude/scheduled_tasks.lock` — gitignore it; the duplicated `docs/prompts/sprint-4.5-employee-profiles.md` — dedupe/remove). Confirm `.gitignore` covers `.env`, `commander.db`, workspaces, `__pycache__`, node_modules, the lock file.
- Commit+push: `chore(release): packaging, README front door, tree cleanup`

## Phase 4 — Release verification & tagging

- **Full green**: `make test` (157+ passing, adjust only for legitimate changes), `tsc --noEmit`, `next build` all clean.
- **Two documented E2E runs**, results recorded in DECISIONS.md:
  1. Mock mode, fresh Postgres volume: `make dev` → found company → starter mission → full pipeline → CEO Decision → completion → Timeline/Payroll/Report all coherent. Simulation-mode label visible.
  2. Real mode (if key available): same flow against Anthropic; confirm coherent output, cost captured, Verdict/section parsing holds on real output. If no key, `make verify-llm` documented as the one-command check and this flagged as the single carryover.
- **Docs final sync**: README, CLAUDE.md (Current Status → "V1 released"; keep the V1/V1.5 boundary note), ARCHITECTURE.md (final V1 module/datastore state), DECISIONS.md Sprint 8 section. Confirm no doc claims a capability V1 doesn't have (especially: don't imply the Engineer iterates or self-fixes).
- **Tag the release**: `git tag v1.0.0` with an annotated message summarizing the V1 surface; push the tag. This is the V1 release marker.
- Commit+push: `chore(release): v1.0.0 verification & docs`; confirm remote HEAD + tag present.

---

## Out of scope (V1.5+ — do not build)

Everything in the Hard boundary list; any new product capability; visual redesign; performance/scaling work on the in-process event bus; real cloud "Launch". Note candidates in DECISIONS.md; don't implement.

## Definition of Done

A newcomer clones the repo, has Docker, follows the README, and within minutes runs `make dev`, founds a company, watches PM→Engineer→Reviewer complete a mission with a real code deliverable and sandboxed checks, makes a CEO Decision, and reads a completion report — with a clear, honest "Simulation mode" label in mock and coherent real output when a key is connected. Every page has intentional empty/loading/error states, no terminology leaks, no fabricated data, no raw errors. `make test` + `next build` clean. `v1.0.0` tagged and pushed. `PROGRESS.txt` 100% honest. Remote HEAD = final commit. **Commander V1 is released.**

---

## Appendix A — PROGRESS.txt checklist (create verbatim, header included)

```
================================================
 COMMANDER — SPRINT PROGRESS
 Sprint: 8 — V1 Release
 Overall: 0/28 items · 0%
 Now working on: —
 Last update: (set on creation)
================================================

PHASE 0 — Fresh-Machine Audit                                  (0/4)
[ ] 0.1  Fresh-clone README dry run; record friction
[ ] 0.2  Click through all 10 pages (mock; real if key) -> rough-edge list
[ ] 0.3  Fold findings into Phases 1-4 as + items + DECISIONS.md
[ ] 0.4  Create PROGRESS.txt; commit+push phase 0

PHASE 1 — Experience Coherence                                 (0/6)
[ ] 1.1  Empty states on all 10 routes (invitation to act)
[ ] 1.2  Loading states (no layout jump) on all data views
[ ] 1.3  Error states (Commander-voiced, no raw errors)
[ ] 1.4  Terminology sweep (no internal-term leaks; StatusWord everywhere)
[ ] 1.5  Copy voice consistency (interface vs company voice)
[ ] 1.6  Commit+push: feat(polish) coherence

PHASE 2 — Demo Honesty                                         (0/5)
[ ] 2.1  "Simulation mode" indicator in mock (hidden in real)
[ ] 2.2  Strengthen mock deliverable/audit honesty signal
[ ] 2.3  Settings: legible mock<->real switch + consequences
[ ] 2.4  Confirm zero fabricated checks/costs/activity anywhere
[ ] 2.5  Commit+push: feat(polish) simulation labeling

PHASE 3 — Packaging & One-Command Run                          (0/7)
[ ] 3.1  README front door (portfolio-facing, verbatim-correct commands)
[ ] 3.2  make ergonomics (+ make help; optional make demo)
[ ] 3.3  .env.example complete with comments + real-key path
[ ] 3.4  Sandbox optionality documented clearly
[ ] 3.5  Remove .claude/scheduled_tasks.lock (gitignore it)
[ ] 3.6  Dedupe docs/prompts/sprint-4.5 file; verify .gitignore coverage
[ ] 3.7  Commit+push: chore(release) packaging

PHASE 4 — Release Verification & Tag                           (0/6)
[ ] 4.1  make test + tsc --noEmit + next build all clean
[ ] 4.2  E2E run #1: mock, fresh PG volume (recorded)
[ ] 4.3  E2E run #2: real Anthropic (or verify-llm + flagged carryover)
[ ] 4.4  Docs final sync (no overclaiming Engineer capability)
[ ] 4.5  git tag v1.0.0 (annotated) + push tag
[ ] 4.6  Commit+push: chore(release) v1.0.0; confirm remote HEAD + tag
================================================
```