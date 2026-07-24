# MISSION: Commander Sprint 5 — Workspace (Real Code, No Execution)

Read `CLAUDE.md`, `docs/ARCHITECTURE.md`, and `docs/design/UX_SPEC.md` (§3.7 is this sprint's UX requirement) first. All rules and the PROGRESS.txt discipline apply. Work autonomously start to finish; do NOT pause for confirmation; log judgment calls in `docs/DECISIONS.md` ("Sprint 5"); commit per phase. Prerequisite: Sprint 4.7 merged (`108a615`), 75/75 tests green.

**Sprint goal:** Employees produce REAL code in a real git workspace — branches, commits, diffs — and the CEO reviews it summary-first, never code-first. This is Phase D's first half.

**⚑ ABSOLUTE GATE (from ARCHITECTURE.md): no AI-generated code is EVER executed this sprint.** No running scripts, no installing its dependencies, no eval, no spawning processes from workspace content — not even "just to check it works". The Reviewer audits statically. Execution arrives only with the Sprint 6 sandbox. If any part of your implementation is tempted to execute workspace content, that temptation is a design error — stop and restructure.

Reset `PROGRESS.txt` for Sprint 5 from Appendix A before feature work.

---

## Design decisions (approved — do not re-litigate)

- **Workspace = one real git repo per company**, at `${COMMANDER_WORKSPACE_ROOT}/{project_id}` (env, default `./workspaces`, gitignored in the Commander repo). Plain `git` CLI via an async subprocess wrapper inside `workspace_manager` — no GitPython/pygit2. Initialized lazily on the first code mission (with a README committed to main), emitting `workspace.initialized`.
- **Branch-per-mission**: `mission/{short_task_id}`. Engineer output lands as ONE commit per attempt on that branch. CEO **Approve → merge to main** (then normal completion). **Request changes → new commit on the same branch** (attempt+1, existing re-run loop). **Reject → branch left unmerged** (history preserved, never deleted).
- **File-block output contract.** The Engineer's role contract (in the software_company template) gains a strict output format for code missions:
  `===== FILE: relative/path.ext =====` … file content … `===== END FILE =====`, one block per file, plus a `**Change Summary:**` section (2–4 plain-language sentences: what changed, why, one potential risk) BEFORE the file blocks. Parse file blocks strictly; parse the summary leniently. **If zero valid file blocks are found, the deliverable gracefully falls back to a document mission (current behavior) — never a pipeline failure.** MockProvider emits deterministic multi-file output (e.g. a tiny static site or module: 2–4 small files) with plausible edits on re-runs.
- **Deliverable type is a mission-level field**: `deliverable_type: "code" | "document"`, chosen at Mission creation (default from the template = `code`; the create-modal gets a simple toggle). The Mission detail renderer is keyed by it (§10.3 — keyed renderer already the rule).
- **Write safety (hard requirements):** every path is validated before write — must be relative, must resolve inside the mission's workspace after normalization (reject `..`, absolute paths, symlink escapes), no writes to `.git/`. Limits: ≤ 30 files per attempt, ≤ 256 KB per file, text only (reject NUL bytes). Violations skip the offending file, emit a system event with the reason, and continue with the valid ones.
- **Reviewer audits the real diff, statically.** The Reviewer's input for code missions includes the Engineer's Change Summary + the actual `git diff` (truncated to a sane token budget with a note when truncated). Its role contract keeps the existing Problem/Recommendation/Risk/Impact sections + trailing Verdict — unchanged hard contract.
- **Merge conflicts can't normally occur** (sequential single-branch writes), but if a merge fails anyway: mission → blocked with a plain-language reason event; no auto-resolution. CEO sees "Blocked — see why".
- **Events**: `workspace.initialized`, `code.changed` (payload: branch, commit sha, files added/modified/deleted counts, +/− line stats, summary), `branch.merged`. All `kind: system`; the Change Summary itself also lands as a conversation event from the Engineer (so it reads naturally in Meetings/Timeline).

---

## Phases

**Phase 1 — WorkspaceManager (backend core).** Implement the existing `core/interfaces/workspace_manager.py` interface with the local-git backend (async subprocess wrapper; repo init, create_branch, write-files-with-validation, commit, diff, merge, file-tree/read for main). Unit tests against temp dirs incl. path-traversal, size/count limits, NUL rejection. Commit: `feat(workspace): local git workspace manager`

**Phase 2 — Contracts & template.** `deliverable_type` on tasks (+API+TS regen); Engineer role contract updated with the file-block format + Change Summary (code missions only — document missions keep today's contract); new event types + payload models; MockProvider deterministic code output; strict block parser + lenient summary parser with the document fallback. Commit: `feat(contracts): code deliverable contract`

**Phase 3 — Pipeline integration.** Workflow engine, code missions: lazy workspace init → branch → parse Engineer output → validated writes → commit → `code.changed` → Reviewer receives summary+diff → approval as today. Decision actions wired: approve→merge (`branch.merged`)→complete; request changes→same branch next attempt; reject→unmerged. Blocked-on-merge-failure path. Streaming, Payroll, retries all still work. Commit: `feat(pipeline): code missions end-to-end`

**Phase 4 — Frontend (§3.7 strictly).** New `/company/[id]/workspace` page (sidebar between Reports and Settings): read-only file tree + file viewer of main, recent merges list. Mission detail for code missions leads with the **ChangeSummaryCard** — plain-language summary + "N files · +A/−B" + audit verdict chip; expansion level 1: file list with per-file stat lines; level 2: unified diff viewer (simple, monospace, add/del coloring — no external heavy deps). **The diff is NEVER the landing view.** DecisionCards for code missions show the summary stats line so the CEO can decide without opening code. Timeline renders `code.changed`/`branch.merged` as compact system rows. Empty workspace state invites the first code mission. `tsc --noEmit` + `next build` clean. Commit: `feat(dashboard): workspace + change summary views`

**Phase 5 — Verification & doc sync.** Tests: block parser (valid/malformed/zero-blocks fallback), path safety suite, branch lifecycle (approve-merge / request-changes-recommit / reject-unmerged), diff-truncation note, document missions fully unaffected. All 75 existing tests green. Live mock E2E: create code mission → watch pipeline → ChangeSummaryCard → expand to diff → approve from /decisions → merge lands on main → workspace page shows the files → request-changes loop on a second mission → verify second commit on same branch. Update CLAUDE.md (status + workspace layout note + gate reminder), ARCHITECTURE.md (workspace_manager ✅, new events, workspace page), DECISIONS.md. Commit: `chore(sprint5): tests, verification, doc sync`

## Out of scope

ANY execution of workspace content (Sprint 6 sandbox), running tests inside workspaces, dependency installation, multi-repo per company, remote git hosting/push, PR-style review UI, syntax highlighting libraries beyond trivial, deleting branches, auth.

## Definition of Done

`make seed && make dev` → create a code Mission → pipeline runs → Engineer's Change Summary reads like a colleague's update → Mission detail shows summary-first, diff two levels deep → approve from /decisions → `branch.merged` in Timeline → `/workspace` shows the merged files on main → run a second code mission, Request changes → same branch gains a new commit → all tests green → zero executions of workspace content anywhere → `PROGRESS.txt` 100% honest.

---

## Appendix A — PROGRESS.txt checklist (create verbatim)

```
================================================
 COMMANDER — SPRINT PROGRESS
 Sprint: 5 — Workspace
 Overall: 0/44 items · 0%
 Now working on: —
 Last update: (set on creation)
================================================

PHASE 1 — WorkspaceManager                                     (0/9)
[ ] 1.1  Async git subprocess wrapper
[ ] 1.2  Lazy repo init + README on main (+ workspace.initialized)
[ ] 1.3  create_branch / commit / merge / diff / file-tree / read
[ ] 1.4  Path validation (relative-only, no .., no symlink escape, no .git)
[ ] 1.5  Limits: 30 files / 256KB / text-only (skip+event on violation)
[ ] 1.6  COMMANDER_WORKSPACE_ROOT env + gitignore
[ ] 1.7  Unit tests: temp-dir git ops
[ ] 1.8  Unit tests: path-safety suite
[ ] 1.9  Commit: feat(workspace)

PHASE 2 — Contracts & Template                                 (0/8)
[ ] 2.1  deliverable_type on tasks + API + TS regen
[ ] 2.2  Engineer contract: FILE blocks + Change Summary (code only)
[ ] 2.3  Events: workspace.initialized / code.changed / branch.merged
[ ] 2.4  Strict block parser
[ ] 2.5  Lenient summary parser
[ ] 2.6  Zero-blocks -> document fallback (never failure)
[ ] 2.7  MockProvider deterministic multi-file output + re-run edits
[ ] 2.8  Commit: feat(contracts)

PHASE 3 — Pipeline Integration                                 (0/9)
[ ] 3.1  Code-mission flow: init -> branch -> write -> commit
[ ] 3.2  code.changed with stats payload
[ ] 3.3  Reviewer input: summary + truncated real diff
[ ] 3.4  Approve -> merge -> branch.merged -> complete
[ ] 3.5  Request changes -> same-branch recommit (attempt+1)
[ ] 3.6  Reject -> branch left unmerged
[ ] 3.7  Merge-failure -> blocked with plain reason
[ ] 3.8  Streaming / Payroll / retries unaffected (verified)
[ ] 3.9  Commit: feat(pipeline)

PHASE 4 — Frontend                                             (0/10)
[ ] 4.1  /workspace page + sidebar item (tree + file viewer + merges)
[ ] 4.2  ChangeSummaryCard (summary, N files +A/-B, verdict chip)
[ ] 4.3  Expansion 1: per-file stat list
[ ] 4.4  Expansion 2: unified diff viewer
[ ] 4.5  Diff never the landing view (mission detail leads with summary)
[ ] 4.6  DecisionCard stats line for code missions
[ ] 4.7  Timeline rows for code.changed / branch.merged
[ ] 4.8  Mission create: deliverable toggle (default code)
[ ] 4.9  tsc --noEmit + next build clean
[ ] 4.10 Commit: feat(dashboard)

PHASE 5 — Verification & Doc Sync                              (0/8)
[ ] 5.1  Tests: parser valid/malformed/fallback
[ ] 5.2  Tests: branch lifecycle (3 decision outcomes)
[ ] 5.3  Tests: diff truncation note
[ ] 5.4  Tests: document missions unaffected
[ ] 5.5  All 75 pre-existing tests green
[ ] 5.6  Live mock E2E per Definition of Done
[ ] 5.7  CLAUDE.md + ARCHITECTURE.md + DECISIONS.md sync
[ ] 5.8  Commit: chore(sprint5)
================================================
```