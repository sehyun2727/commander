# MISSION: Commander Sprint 4.5 (FINAL) — Employee Profiles + Live Progress Tracking + Repo Docs Sync

Prerequisite: Sprint 4 is merged (verified: commits through `70924b8`, 42/42 tests green). Read `Claude.md` at repo root first (Phase 0 renames it to `CLAUDE.md` — its content is current and authoritative). Work autonomously; log judgment calls in `docs/DECISIONS.md` under "Sprint 4.5"; commit per phase.

Three deliverables, in this order:
- **Phase 0.** Repo documentation sync (one-time housekeeping)
- **Part A.** A permanent live progress-tracking system (`PROGRESS.txt`) — standard practice for ALL future sprints
- **Part B.** The Agent Personality Profile system (approved FR)

---

## PHASE 0 — Repo Docs Sync (before anything else)

1. **Reseed the dev DB**: run `make seed` to clear the Sprint 4 verification cruft (the leftover "Phase3 verification mission" pending decision and test-generated Daily Reports in Acme AI). This is the approved answer to the open reseed question.
2. **Rename `Claude.md` → `CLAUDE.md`**. You are on a case-insensitive filesystem (Windows), so use the two-step: `git mv Claude.md CLAUDE_tmp.md && git mv CLAUDE_tmp.md CLAUDE.md`. Content stays untouched.
3. **Create `docs/design/UX_SPEC.md`** with EXACTLY the content between the `===== FILE BEGIN/END =====` markers at the bottom of this brief (markers not included). Do not summarize or reword — verbatim. This is the product experience source of truth (v1.1, includes the Future Expansion Strategy).
4. **Add pointers to `CLAUDE.md`**: in the Repo Layout block add two lines — `docs/design/UX_SPEC.md   product experience source of truth — ALL frontend work follows it` and `docs/prompts/      sprint briefs`. In Working Style add: `Maintain PROGRESS.txt per the live progress discipline (see docs/prompts/) — update per item, never batched.`
5. **Save this brief** (everything above the FILE BEGIN marker) to `docs/prompts/sprint-4.5-employee-profiles.md`.
6. Commit: `chore: repo docs sync (CLAUDE.md rename, UX spec v1.1, sprint brief)`

Roadmap context so you can orient future work: Sprints 0–4 complete → **4.5 (this)** → 4.7 "Headquarters UX" (UX_SPEC §3 core application + §10.6 internal-template refactor) → 5 Workspace → 6 Execution Sandbox → 7 Launch → 8 Release Polish → MVP. Do not start 4.7+ work now.

---

## PART A — Progress Tracking System (before any feature code)

### The rule

Commander development must be observable to the CEO — the same principle the product applies to agents now applies to you. From this sprint forward, `PROGRESS.txt` at the repo root shows real-time work status. The CEO opens this file to see progress, so it must always reflect reality.

### Update discipline (MANDATORY)

1. Create `PROGRESS.txt` from the checklist in Appendix A, all items `[ ]`, BEFORE writing any feature code (Phase 0 counts — backfill its items as `[x]` when you create the file).
2. Mark an item `[~]` the moment you start it, `[x] @HH:MM` the moment it's done. Update **immediately per item** — never batch at the end of a phase.
3. Work you discover mid-sprint gets ADDED as a new `+` item — never done silently.
4. Blocked items: `[!]` + one-line reason. Never delete or reword completed items.
5. Recompute the phase counters and the top summary block on every touch.
6. `PROGRESS.txt` rides along in each phase commit.

### Markers & header

```
[ ] not started   [~] in progress   [x] done @HH:MM   [!] blocked (reason)   + discovered
```

```
================================================
 COMMANDER — SPRINT PROGRESS
 Sprint: 4.5 — Employee Profiles
 Overall: 0/53 items · 0%
 Now working on: (item id)
 Last update: YYYY-MM-DD HH:MM
================================================
```

---

## PART B — Agent Personality Profile System

### Final decisions (impact review approved — do not re-litigate)

- `AgentORM.persona: Text` is REPLACED by a JSON `profile` column validated by a Pydantic `AgentProfile` model (name, role, personality, working_style, decision_style, custom_instructions, model_ref nullable). Extensible toward future Agent Harness.
- Generated prompts are NEVER stored — always built at runtime so edits apply instantly.
- **PromptBuilder layering is a hard contract:** role contract (immutable, placed LAST so it wins) > personality/working/decision traits > custom instructions. Custom instructions can never remove the role contract — the Reviewer's trailing `**Verdict:**` line must survive ANY profile configuration.
- Trait→behavior text mapping lives in DATA (yaml or a dict module), not code.
- **Model resolution becomes three-tier.** Current code: `RoutedProviderGateway.resolve_model` (apps/api/app/modules/provider_gateway/gateway.py) checks the per-role CEO override via `model_registry.get_override` for `*-default` refs, else `registry.resolve`. New order: **agent `profile.model_ref` override → role override (settings_kv, Sprint 4) → registry default.** Thread the agent context into the gateway call path however is cleanest (e.g. optional `agent_override` param on `resolve_model`); log your choice.
- Custom instructions: plain text, 500 chars max.
- No migrations: dev DBs reset via `make seed`; update seed.py for the new schema.

### Phases

**Phase 1 — Contracts & Model**: `AgentProfile` model + enums (Personality: professional/friendly/direct/conservative · WorkingStyle: fast/balanced/detail_oriented · DecisionStyle: risk_avoiding/balanced/experimental) in the contracts package; new event `agent.profile_updated` + payload model; regenerate TS; AgentORM `persona` → `profile` JSON; default per-role profiles as data; founding uses them; seed.py updated.

**Phase 2 — PromptBuilder**: `modules/prompt_builder/` — pure functions, no DB/provider imports. `build(profile, role) -> str` with the layering contract; trait mapping data file; role contracts for PM/Engineer/Reviewer (Reviewer's includes the Verdict output requirement); 500-char cap enforced.

**Phase 3 — Profiles API**: `modules/agent_profiles/` — GET/PUT `/agents/{id}/profile`; PUT validates, persists, emits `agent.profile_updated` (payload lists changed fields only); Timeline copy: "CEO updated {name}'s profile"; error cases (bad enum, over-cap, unknown agent).

**Phase 4 — Runtime Integration**: workflow_engine (`system=agent.persona`, currently line ~256) → `prompt_builder.build(...)`; three-tier model resolution wired; the Sprint 4 streaming path (engine ~line 208) must keep working with built prompts; Payroll/cost attribution unaffected (verify — costs.record_usage takes role/model per call); MockProvider gains light personality flavor (conservative mentions risks, friendly is warmer) so profiles are demoable with zero API keys.

**Phase 5 — Frontend (per UX_SPEC §3.4)**: Employee profile page/drawer — role & responsibility, model shown as plain name, three style selects, custom-instructions textarea (500 cap + counter), save + toast; profile changes appear live in Timeline via SSE; Employee cards get a one-line style summary; Commander terminology on every new string; `tsc --noEmit` + `next build` clean.

**Phase 6 — Verification & Doc Sync**: pytest — PromptBuilder layering incl. **adversarial custom-instruction Verdict-survival case**, profile CRUD + event emission, three-tier model resolution, founding defaults; all 42 existing tests stay green; mock-mode live E2E per Definition of Done; update CLAUDE.md (Current Status + PROGRESS.txt discipline line if not already added), ARCHITECTURE.md module table (+agent_profiles, +prompt_builder), DECISIONS.md.

### Out of scope

Agent Harness, tools/memory/budget fields, per-agent provider (model override only), Sprint 4.7 UX_SPEC application, performance history UI beyond basics, auth.

### Definition of Done

`make seed && make dev` → open an Employee profile → set Engineer to conservative + detail-oriented + custom instruction "Always explain risks before coding" → Timeline shows the change → run a Mission → Engineer's output visibly reflects the profile (mock mode) → Reviewer still emits a parseable Verdict → approve the CEO Decision → mission completes → Payroll still accumulates → all tests green → `PROGRESS.txt` reads 100% with honest timestamps.

---

## Appendix A — PROGRESS.txt initial checklist (create verbatim, header included)

```
================================================
 COMMANDER — SPRINT PROGRESS
 Sprint: 4.5 — Employee Profiles
 Overall: 0/53 items · 0%
 Now working on: —
 Last update: (set on creation)
================================================

PHASE 0 — Repo Docs Sync                                       (0/6)
[ ] 0.1  make seed (clear verification cruft)
[ ] 0.2  Rename Claude.md -> CLAUDE.md (two-step git mv)
[ ] 0.3  Create docs/design/UX_SPEC.md (verbatim from brief)
[ ] 0.4  CLAUDE.md pointer lines (UX_SPEC, prompts, PROGRESS discipline)
[ ] 0.5  Save brief to docs/prompts/sprint-4.5-employee-profiles.md
[ ] 0.6  Commit: chore: repo docs sync

PHASE 1 — Contracts & Model                                    (0/9)
[ ] 1.1  AgentProfile Pydantic model (incl. model_ref nullable)
[ ] 1.2  Enums: Personality / WorkingStyle / DecisionStyle
[ ] 1.3  Event agent.profile_updated + payload model
[ ] 1.4  Regenerate TS types
[ ] 1.5  AgentORM: persona Text -> profile JSON
[ ] 1.6  Default role profiles as data (PM/Engineer/Reviewer)
[ ] 1.7  Founding uses default profiles
[ ] 1.8  seed.py updated
[ ] 1.9  Commit: feat(profiles): contracts + model

PHASE 2 — PromptBuilder                                        (0/7)
[ ] 2.1  modules/prompt_builder/ (pure, no DB/provider deps)
[ ] 2.2  Trait mapping data file
[ ] 2.3  build(profile, role): traits + custom instructions
[ ] 2.4  Role contract layer appended LAST (immutable)
[ ] 2.5  Reviewer contract includes Verdict requirement
[ ] 2.6  500-char custom instruction cap
[ ] 2.7  Commit: feat(prompt-builder): layered prompt construction

PHASE 3 — Profiles API                                         (0/6)
[ ] 3.1  GET /agents/{id}/profile
[ ] 3.2  PUT with validation
[ ] 3.3  Emit agent.profile_updated (changed fields only)
[ ] 3.4  Timeline copy for profile changes
[ ] 3.5  Error cases (bad enum, over-cap, unknown agent)
[ ] 3.6  Commit: feat(profiles): CRUD API + events

PHASE 4 — Runtime Integration                                  (0/7)
[ ] 4.1  workflow_engine: system prompt via PromptBuilder
[ ] 4.2  Three-tier model resolution (agent > role > default)
[ ] 4.3  MockProvider personality flavor
[ ] 4.4  Streaming path still works with built prompts
[ ] 4.5  Payroll/cost attribution unaffected (verified)
[ ] 4.6  Retry/backoff path unaffected (verified)
[ ] 4.7  Commit: feat(runtime): profile-driven prompts

PHASE 5 — Frontend                                             (0/10)
[ ] 5.1  Employee profile page/drawer + data hooks
[ ] 5.2  Display: role, model plain name, style summary
[ ] 5.3  Three style selects
[ ] 5.4  Custom instructions textarea + 500 counter
[ ] 5.5  Save flow + toast
[ ] 5.6  Profile change live in Timeline (SSE)
[ ] 5.7  Employee cards: one-line style summary
[ ] 5.8  Commander terminology check on new strings
[ ] 5.9  tsc --noEmit + next build clean, zero console errors
[ ] 5.10 Commit: feat(dashboard): employee profile editing

PHASE 6 — Verification & Doc Sync                              (0/8)
[ ] 6.1  Tests: layering + adversarial Verdict survival
[ ] 6.2  Tests: profile CRUD + event emission
[ ] 6.3  Tests: three-tier model resolution
[ ] 6.4  Tests: founding default profiles
[ ] 6.5  All 42 pre-existing tests green
[ ] 6.6  Mock-mode live E2E (per Definition of Done)
[ ] 6.7  CLAUDE.md status + ARCHITECTURE.md table + DECISIONS.md
[ ] 6.8  Commit: chore(sprint4.5): tests + doc sync
================================================
```
