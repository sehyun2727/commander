# MISSION: Commander Sprint 6 — Execution Sandbox

Read `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/design/UX_SPEC.md` first. All rules and the PROGRESS.txt discipline apply. Work autonomously; do NOT pause for confirmation; log judgment calls in `docs/DECISIONS.md` ("Sprint 6"); commit AND PUSH per phase. Prerequisite: Sprint 5 merged (`30b5aaa`), 113 tests.

**Sprint goal:** AI-generated code can finally RUN — but only inside an isolated Docker sandbox, only via trusted commands, with results feeding the Reviewer and the CEO Decision. This lifts the Sprint 5 execution gate in exactly one controlled place and nowhere else.

## Security model (the whole sprint hangs on these — never weaken them)

1. **Docker-only, no fallback.** If Docker is unavailable, execution features disable gracefully (product fully works without them, as today). NEVER fall back to executing workspace content on the host — not "temporarily", not "for tests", not in test code.
2. **The AI never chooses what command runs.** Check commands come exclusively from trusted template data (`software_company` template). AI-generated code is only ever INPUT FILES to those commands. If you find yourself interpolating model output into a command line, stop — design error.
3. **Container constraints (all mandatory):** `--network none` · `--memory 512m` · `--cpus 1` · `--pids-limit 256` · non-root user · `--rm` · hard timeout 120s (kill the container, not just the process) · combined output captured with a 10,000-char tail cap · NEVER mount the Docker socket · workspace enters the container via `docker cp`/tar stream into a created container, NOT a bind mount (avoids Windows/OneDrive mount issues entirely and guarantees the host copy can't be modified — results only come back as captured output, never as files).
4. Sandbox failures are events, never crashes: image missing, daemon down, timeout, OOM — each becomes a plain-language system event and the mission continues (checks reported as "could not run"), pipeline never dies on sandbox trouble.

## Design decisions (approved — do not re-litigate)

- **`SandboxRunner` interface** in `core/interfaces/` + `DockerSandbox` implementation in a new `modules/sandbox/` module; plus a `FakeSandbox` for tests. This is the Cloud Runner abstraction point from the original architecture — cloud execution later swaps the implementation, nothing else.
- **Sandbox image**: one `commander-sandbox` image built from `sandbox/Dockerfile` in the repo — `python:3.12-slim` base + Node LTS + pytest preinstalled at build time. `make sandbox-image` builds it. Containers run with no network, so v1 supports **preinstalled runtimes only, no dependency installation**; add one line to the Engineer's role contract: generated code must run with the Python stdlib / Node built-ins (+ pytest) only, for now.
- **Checks are template data**: the template gains `checks: [{name, detect_glob, command}]` — v1 for software_company: `pytest` (detect `**/test_*.py` → `python -m pytest -q`), `node-test` (detect `**/*.test.{js,mjs}` → `node --test`), and a always-on `python-syntax` (`python -m compileall -q .`) when any `.py` exists. Detection runs on the mission branch's files; only matched checks run.
- **Pipeline position**: after the Engineer's commit, before the Reviewer. Events: `execution.started` → per-check results → `execution.completed` (payload: per-check name/passed/duration/output-tail, overall pass count). The Reviewer's input gains the results; its contract/Verdict stay unchanged. **Failed checks do not auto-fail the mission** — the Reviewer weighs them (its Risk section should mention failures), and the CEO decides; the natural request-changes loop handles fixes.
- **Capability surface**: `GET /api/system/capabilities` → `{execution: bool, reason?: string}` (docker + image probed at startup, cached, re-probed on demand). Company Settings shows execution status ("Execution enabled" / "Requires Docker Desktop — [how-to link]") plus an on/off toggle (settings_kv) for companies that want plan-only mode.
- **CEO-facing copy**: results render as plain verdicts — "All 3 checks passed" / "1 of 3 checks failed" — never raw tracebacks at L1. Output tails live at disclosure level 2+.

## Phases

**Phase 0 — Hygiene (small, do first).**
(a) Fix the platform-dependent path validation found in external review: `validate_path` accepts `C:\evil`-style Windows drive paths on POSIX systems (PurePosixPath doesn't consider them absolute; the resolve backstop only catches them on Windows). Add an explicit drive-letter rejection (`^[A-Za-z]:` after backslash normalization) so behavior is identical on every platform — this matters NOW because sandbox containers are Linux. Make `test_validate_path_rejects_windows_drive_absolute` pass on both platforms.
(b) Add the standing rule to CLAUDE.md Working Style (it was requested previously but never landed): "Every sprint's final phase commit must be followed by `git push`; a sprint is not complete until the remote HEAD matches the final commit."
Commit+push: `fix(workspace): platform-independent path validation; docs: push rule`

**Phase 1 — Sandbox core.** `SandboxRunner` interface; `sandbox/Dockerfile` + `make sandbox-image`; `DockerSandbox` (create container → tar-copy workspace in → run check command under all constraints → capture → destroy); capability probe + endpoint; `FakeSandbox`. Unit tests with FakeSandbox for orchestration logic; real-Docker tests marked `@pytest.mark.skipif` on capability. Commit+push: `feat(sandbox): docker sandbox runner`

**Phase 2 — Checks & pipeline.** Template `checks` data + detection; pipeline step between Engineer commit and Reviewer (execution events, per-check results, timeout/daemon-down/no-image degradation paths); Reviewer input includes results; execution toggle honored; streaming/Payroll/retries unaffected. Commit+push: `feat(pipeline): sandboxed checks`

**Phase 3 — Frontend.** Mission detail: ExecutionResults section — per-check chips (pass green / fail red / could-not-run gray) + duration, expandable output tail at level 2; ChangeSummaryCard + DecisionCard gain the plain checks verdict line; Timeline rows for execution events (CEO view shows the verdict row, Technical view shows per-check rows); Settings execution status + toggle; capability-driven graceful hiding when Docker absent. `tsc --noEmit` + `next build` clean. Commit+push: `feat(dashboard): execution results`

**Phase 4 — Verification & doc sync.** Tests: detection matrix, degradation paths (no docker / no image / timeout), results→Reviewer input, toggle off skips execution, path-fix regression; all pre-existing tests green; if Docker is available locally run the real E2E (code mission → checks run in container → chips render → approve), otherwise FakeSandbox E2E + note in DECISIONS.md that real-Docker verification is pending. Update CLAUDE.md (status, sandbox module, capability note), ARCHITECTURE.md (sandbox ✅, security model summary, Cloud Runner extraction point), DECISIONS.md. Final commit+push: `chore(sprint6): tests, verification, doc sync` — confirm remote HEAD matches.

## Out of scope

Dependency installation / network in containers, cloud execution, arbitrary CEO-authored commands, deployment/Launch (Sprint 7), running checks for document missions, Windows containers, docker-compose orchestration, auth.

## Definition of Done

With Docker: `make sandbox-image && make seed && make dev` → code Mission → Timeline shows "Running checks" → mission detail shows per-check chips → Reviewer's Risk mentions any failures → DecisionCard reads "All checks passed" (or counts) → approve → merge. Without Docker: identical flow minus execution, Settings explains why, zero errors anywhere. All tests green on both. `PROGRESS.txt` 100% honest. Remote HEAD = final commit.

---

## Appendix A — PROGRESS.txt checklist (create verbatim)

```
================================================
 COMMANDER — SPRINT PROGRESS
 Sprint: 6 — Execution Sandbox
 Overall: 0/40 items · 0%
 Now working on: —
 Last update: (set on creation)
================================================

PHASE 0 — Hygiene                                              (0/4)
[ ] 0.1  Drive-letter rejection in validate_path (platform-independent)
[ ] 0.2  Path test green on POSIX and Windows semantics
[ ] 0.3  CLAUDE.md push rule added
[ ] 0.4  Commit+push: fix(workspace)/docs

PHASE 1 — Sandbox Core                                         (0/10)
[ ] 1.1  SandboxRunner interface (core/interfaces)
[ ] 1.2  sandbox/Dockerfile (python3.12-slim + node LTS + pytest)
[ ] 1.3  make sandbox-image
[ ] 1.4  DockerSandbox: create -> tar-copy in -> run -> capture -> destroy
[ ] 1.5  All constraints: no-net, mem, cpu, pids, non-root, rm, 120s kill
[ ] 1.6  Output tail cap 10k chars
[ ] 1.7  Capability probe + GET /api/system/capabilities
[ ] 1.8  FakeSandbox for tests
[ ] 1.9  Unit tests (Fake) + skipif real-Docker tests
[ ] 1.10 Commit+push: feat(sandbox)

PHASE 2 — Checks & Pipeline                                    (0/9)
[ ] 2.1  Template checks data (pytest / node-test / python-syntax)
[ ] 2.2  Detection on mission branch files
[ ] 2.3  Pipeline step: after commit, before Reviewer
[ ] 2.4  Events: execution.started / execution.completed (payloads)
[ ] 2.5  Degradation: no docker / no image / timeout -> events, never crash
[ ] 2.6  Reviewer input includes results
[ ] 2.7  Execution toggle (settings_kv) honored
[ ] 2.8  Streaming / Payroll / retries unaffected (verified)
[ ] 2.9  Commit+push: feat(pipeline)

PHASE 3 — Frontend                                             (0/9)
[ ] 3.1  ExecutionResults section (chips + duration)
[ ] 3.2  Output tail at disclosure level 2
[ ] 3.3  ChangeSummaryCard + DecisionCard checks verdict line
[ ] 3.4  Timeline rows (CEO verdict row / Technical per-check)
[ ] 3.5  Settings: capability status + toggle
[ ] 3.6  Graceful hiding when Docker absent
[ ] 3.7  Engineer contract line: stdlib/built-ins only (v1)
[ ] 3.8  tsc --noEmit + next build clean
[ ] 3.9  Commit+push: feat(dashboard)

PHASE 4 — Verification & Doc Sync                              (0/8)
[ ] 4.1  Tests: detection matrix
[ ] 4.2  Tests: degradation paths
[ ] 4.3  Tests: toggle-off skips execution
[ ] 4.4  Tests: path-fix regression
[ ] 4.5  All pre-existing tests green
[ ] 4.6  E2E (real Docker if available, else Fake + DECISIONS note)
[ ] 4.7  CLAUDE.md + ARCHITECTURE.md + DECISIONS.md sync
[ ] 4.8  Final commit+push, remote HEAD confirmed
================================================
```