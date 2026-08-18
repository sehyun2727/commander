# Sprint 16 — Secure Agent Harness

Execute this sprint autonomously from Phase 0 through Phase 5.

Expected baseline:
- local HEAD: d3d6425
- origin/master: d3d6425
- backend baseline: 373 passed / 4 skipped
- dashboard typecheck/build: PASS
- migration round-trip and fresh bootstrap: PASS
- mock E2E with zero provider keys: PASS
- browser-rendered interaction verification: UNVERIFIED

Repository and git state are authoritative. Verify every baseline claim first.

Follow the current CLAUDE.md, architecture, decisions, UX specification, security constraints, progress discipline, verification standards, and reporting format.

Do not stop for routine confirmation. Stop only for a hard blocker, destructive ambiguity, security/cost exposure, or irreconcilable architectural conflict.

---

## 1. Goal

Build Commander’s first secure Agent Harness: a bounded, server-owned runtime through which Employees may request approved tools without receiving unrestricted host access.

At the end of Sprint 16:

1. Tools are defined in one canonical, immutable server registry.
2. Tool access is calculated from Role permissions, Employee skill template, mission context, and server policy.
3. Agent/provider output can request only structured, typed tool calls.
4. Every call is validated before execution.
5. Repository operations are restricted to an assigned workspace root.
6. Path traversal, symlink escape, arbitrary commands, arbitrary executables, and shell metacharacter injection are blocked.
7. Supported validation commands execute through named allowlisted command profiles.
8. Calls have timeout, output, file-size, invocation-count, and iteration budgets.
9. Calls and results are observable and auditable without leaking secrets.
10. Failures are structured, visible, and cannot silently advance work.
11. Mock mode proves the complete harness flow with zero provider keys.
12. Existing planning, specification, mission, Workspace, and Widget behavior remains functional.

This sprint builds the harness and a bounded repository-aware execution loop.

It does not implement unrestricted shell access, autonomous self-correction, organizational memory, plugins, containers as a platform, or arbitrary user-authored tools.

---

## 2. Security Model

Treat all of the following as untrusted:

- provider output
- tool names
- tool arguments
- file paths
- patch content
- search patterns
- command-profile parameters
- repository contents
- tool output
- environment variables
- stored skill-template metadata

The harness is the security boundary.

Prompt instructions and frontend validation are not security controls.

The server must independently authorize and validate every call.

Default behavior is deny.

---

## 3. Required Repository Inspection

Before changing code, inspect at minimum:

- CLAUDE.md
- PROGRESS.txt and Sprint 16 handoff
- README.md
- docs/ARCHITECTURE.md
- docs/DECISIONS.md, especially Sprint 10–15 decisions
- docs/design/UX_SPEC.md
- git history through d3d6425
- RoleSpec tools/permissions
- skill-template registry
- Employee runtime configuration
- AgentRuntime and PromptBuilder
- provider adapters and structured-output support
- WorkflowEngine and mission stage execution
- mission/task workspace and repository lifecycle
- current code-writing, patching, git, test, merge, and cancellation behavior
- current subprocess, filesystem, or shell usage
- security/path validation utilities
- event types and observability
- auth and company ownership
- migrations and persistence models
- mock provider behavior
- backend tests for code missions, cancellation, retries, and reliability
- dashboard mission/activity/error surfaces

Search specifically for:

- `subprocess`
- `os.system`
- `shell=True`
- `Popen`
- file writes
- git invocation
- arbitrary command strings
- `eval`/`exec`
- archive extraction
- symlink handling
- environment exposure
- provider tool/function calling

Document existing execution paths before replacing or wrapping them.

---

## 4. Approved Decisions

### 4.1 Canonical first-party Tool Registry

Create one immutable server-owned registry.

Each tool definition should contain the smallest necessary typed metadata, equivalent to:

- key
- title
- description
- input schema
- output schema
- risk class
- mutating/read-only classification
- required capabilities
- allowed mission/stage contexts
- default timeout
- maximum output size
- audit policy
- implementation handler reference owned by server code

Do not store or accept executable handler paths from the client, database, RoleSpec, skill templates, or provider.

Tool definitions are code-owned first-party data.

### 4.2 Initial tool set

Implement the smallest coherent set needed for repository-aware coding:

Read-only:
- list repository paths
- read text file
- search repository text
- inspect git status/diff
- optionally inspect a bounded file metadata/stat result

Mutating:
- apply a structured patch
- optionally create a text file through the same patch boundary

Validation:
- run named validation profile
- inspect bounded validation result

Use repository conventions when deciding exact names.

Do not add:

- generic shell
- generic command
- arbitrary executable
- arbitrary package install
- arbitrary network request
- arbitrary Git remote operation
- delete-tree tool
- archive extraction
- process management
- database console
- deployment tool

### 4.3 Named validation profiles

Validation commands must be selected by canonical server-owned profile keys.

Examples may include existing repository commands such as:

- backend targeted tests
- backend full tests
- dashboard typecheck
- dashboard build

Determine actual profiles from repository scripts and Makefile/package configuration.

The provider may select a profile key and bounded allowlisted parameters only.

It must not supply the executable, shell string, environment, working directory, redirection, pipeline, or arbitrary flags.

Execute without `shell=True`.

### 4.4 Workspace root

Every harness run is bound to an authoritative server-selected workspace root.

The root must come from trusted mission/repository state, not provider/client input.

All path operations must:

- normalize paths,
- reject absolute paths,
- reject `..` traversal,
- resolve parent components,
- account for non-existent write targets,
- reject symlink escape,
- reject paths outside the root,
- use bounded path and file lengths.

Do not rely only on string-prefix checks.

### 4.5 Symlink policy

Default policy: reject symlinks for mutating operations and reject any resolved read/search target outside the workspace.

If repository symlinks are supported for reads, they must resolve inside the workspace and be explicitly tested.

Never follow a symlink outside the root.

### 4.6 Patch-only writes

Providers do not receive unrestricted file-write APIs.

Use a structured patch format with validation.

Requirements:

- workspace-relative paths only
- no binary patches
- no symlink writes
- no device/special files
- bounded files per patch
- bounded patch bytes
- bounded resulting file size
- expected-content or base-hash checks where practical
- atomic application or complete rollback
- explicit conflict result
- diff captured after success

Do not silently accept partially applied patches.

### 4.7 Permission calculation

Effective tool access is the intersection of:

- server global policy
- mission/stage policy
- RoleSpec permission/tool declarations
- Employee skill-template capabilities
- runtime state
- repository/workspace availability

No source can grant beyond server global policy.

Missing or unknown permission data means deny.

Do not trust a stored skill-template key to imply arbitrary tools without resolving it through the canonical registry.

### 4.8 Structured tool calls

A tool call must include a server-issued run context and typed fields equivalent to:

- call ID
- run/mission/stage identity
- Employee identity
- tool key
- arguments
- attempt/iteration metadata

Provider-supplied IDs must not become authoritative without validation.

Reject:

- unknown tools
- malformed arguments
- repeated completed call IDs
- calls outside active run state
- calls after cancellation
- calls exceeding budgets
- calls unauthorized for the resolved Employee/stage

### 4.9 Budgets

Enforce server-side bounds for:

- maximum tool calls per iteration
- maximum iterations per stage
- maximum cumulative calls per run
- timeout per tool
- cumulative runtime
- input/patch size
- output bytes
- files read
- search matches
- validation profiles run
- retry count

Use conservative defaults after inspecting current mission complexity.

Budget exhaustion must produce a structured terminal or recoverable result according to policy.

Do not allow infinite tool/provider loops.

### 4.10 Output handling

Tool output is untrusted and bounded.

Requirements:

- truncate safely with explicit metadata
- distinguish stdout/stderr where relevant
- redact known secret patterns and sensitive environment values
- avoid logging complete sensitive files
- never include the entire process environment
- do not return binary data
- normalize encoding errors safely
- preserve enough evidence for debugging

A truncated result must say it was truncated.

### 4.11 Process isolation

Use the strongest practical boundary supported by the current repository without introducing an entire container platform.

At minimum:

- `shell=False`
- explicit argv from server profile
- controlled working directory
- minimal allowlisted environment
- no inherited provider-controlled environment
- timeout with process-tree termination
- captured bounded output
- no stdin
- no interactive process
- no network-enabling command profile unless explicitly required and approved
- no credential forwarding unless a narrowly approved existing workflow requires it

If the repository already has container/worktree isolation, reuse it.

Document residual risk honestly.

Do not claim OS-grade sandboxing if only application-level restrictions exist.

### 4.12 Network default deny

Harness tools must not provide generic network access.

Validation profiles should use offline/no-network modes where practical.

Do not add URL fetch, curl, package installation, or arbitrary remote Git operations.

If an existing code mission requires Git commit behavior, keep it outside provider-controlled arbitrary tool parameters and preserve current server-owned policy.

### 4.13 Human approval boundary

Sprint 16 does not create a broad new approval center.

However, classify tools by risk and define policy hooks for future approvals.

For this sprint:

- read-only and approved validation tools may run automatically when authorized,
- patch application may run only within an already approved code mission/specification and authorized stage,
- destructive, deployment, credential, network, or high-risk tools remain unavailable.

### 4.14 Harness does not equal self-correction

A bounded provider/tool loop may inspect, patch, and validate during one authorized stage.

Do not implement Sprint 17’s generalized:

- failure diagnosis across runs,
- autonomous rollback strategies,
- repeated corrective mission cycles,
- learning from failures,
- escalation policies.

Stop at explicit budget, validation, cancellation, or stage completion boundaries.

---

## 5. Architecture Requirements

Prefer boundaries equivalent to:

- `ToolDefinition` and immutable registry
- capability/permission resolver
- path/workspace guard
- tool-call validator
- tool handlers
- command-profile registry and runner
- patch validator/applier
- output redactor/truncator
- Harness orchestrator
- persistence/audit service
- AgentRuntime integration adapter

The Harness orchestrates authorized calls.

It must not become:

- a generic shell wrapper
- WorkflowEngine replacement
- provider adapter
- prompt builder
- mission API
- event bus
- self-correction engine

Keep pure security-sensitive validation separately testable.

---

## 6. Persistence and Audit

Persist enough structured data to audit execution, unless existing event/run models already provide an equivalent durable record.

Conceptually record:

- harness run ID
- company/project
- mission/task/stage
- Employee
- tool call ID
- tool key
- risk/mutation class
- validated safe argument summary
- status
- started/completed timestamps
- duration
- result summary
- truncation flag
- error code
- authorization decision/reason
- budget counters

Do not persist:

- provider secrets
- complete environment
- raw credential-bearing output
- hidden chain-of-thought
- full sensitive file contents
- unrestricted raw prompts unless already governed safely

Use event records for CEO-visible summaries and a durable audit record for engineering evidence if current architecture separates these concerns.

Success events occur only after successful durable state changes.

---

## 7. AgentRuntime Integration

Extend AgentRuntime/provider interaction so an authorized stage can:

1. receive a bounded repository context,
2. return either:
   - structured tool calls,
   - a structured completion,
   - a structured blocked/failure response,
3. execute authorized tool calls,
4. return bounded results to the provider,
5. continue within the iteration budget,
6. stop on completion, cancellation, failure, or exhaustion.

Provider output must be schema-validated.

Malformed calls use bounded retry according to existing provider policy.

Do not place tool execution inside provider adapters.

Mock mode must deterministically exercise:

- repository read/search,
- patch,
- validation,
- completion,
- denied call,
- budget exhaustion where fixture-selected.

---

## 8. Mission and Workflow Integration

Integrate only into authorized code-changing stages.

Requirements:

- specification approval gate remains intact,
- central Employee resolver remains intact,
- Employee-specific model/skill configuration remains intact,
- cancellation prevents further calls,
- task/Employee cleanup remains intact,
- failed validation cannot silently mark stage successful,
- patch evidence flows into existing review/decision stages,
- existing PM → Engineer → Reviewer semantics remain compatible,
- Reviewer must inspect actual resulting diff/evidence rather than trusting a completion string.

Do not make planning/PM↔CTO stages repository-mutating unless explicitly authorized by current architecture.

---

## 9. API and Dashboard Scope

The Harness should not expose public arbitrary tool-execution endpoints.

Do not create endpoints equivalent to:

- `POST /tools/run`
- `POST /shell`
- `POST /execute-command`

Allowed API changes are limited to safe read-only observability integrated into existing mission/task detail APIs if needed.

The dashboard may display:

- current harness status
- tool name/title
- safe reason
- duration
- success/failure
- truncated-result notice
- validation summary
- budget exhaustion
- denied-call explanation

Do not display:

- raw secret-bearing output
- hidden reasoning
- complete environment
- unrestricted file contents
- executable replay controls

Reuse existing activity/timeline/error surfaces. Do not redesign the Workspace.

---

## 10. Required Threat Tests

Add behavioral tests for at least:

### Tool authorization
- unknown tool denied
- tool absent from Role permission denied
- tool absent from skill capability denied
- wrong mission/stage denied
- cancelled run denied
- cross-company/run identity denied
- provider cannot self-grant tools

### Paths
- absolute path denied
- `..` traversal denied
- encoded/normalized traversal denied where applicable
- prefix-confusion path denied
- symlink escape denied
- non-existent target parent escape denied
- valid internal path accepted
- long path denied
- special file denied

### Patches
- binary patch denied
- oversized patch denied
- too many files denied
- symlink mutation denied
- partial/conflicting patch rolls back
- stale base/hash conflict
- valid multi-file patch succeeds atomically
- resulting diff captured

### Commands
- unknown profile denied
- arbitrary executable denied
- arbitrary flags denied
- shell metacharacters remain inert/denied
- `shell=False` execution path
- controlled cwd
- minimal environment
- timeout kills process tree
- output truncation
- no stdin/interactive use
- validation failure is structured

### Budgets/idempotency
- duplicate call ID safe
- per-iteration limit
- per-run limit
- cumulative timeout
- retry limit
- cancellation during tool
- stale callback after cancellation
- no success after exhaustion

### Data exposure
- secret-like values redacted
- environment not exposed
- binary output rejected
- invalid encoding handled
- raw provider payload not emitted
- safe event/audit serialization

### Integration
- deterministic mock read→patch→validate→complete
- denied mock tool path
- failed validation blocks completion
- existing reviewer flow receives diff/evidence
- existing mission cancellation cleanup
- zero provider keys
- existing planning/workspace/widget regressions absent

---

## 11. Phases

## Phase 0 — Baseline and Threat Model

1. Verify HEAD, origin/master, and working tree.
2. Run backend baseline.
3. Run dashboard typecheck/build.
4. Verify migration/bootstrap.
5. Run current mock code-mission E2E.
6. Inventory every filesystem/process/git execution path.
7. Inventory RoleSpec and skill-template permissions.
8. Inspect provider structured-tool support.
9. Define threat model and trust boundaries.
10. Define initial tools and excluded tools.
11. Define validation command profiles.
12. Define workspace-root source.
13. Define budgets.
14. Define persistence/audit approach.
15. Determine whether schema migration is needed.
16. Replace PROGRESS.txt with Sprint 16 live checklist.
17. Record non-obvious decisions.
18. Commit/push Phase 0 if consistent with repository practice.

## Phase 1 — Registry, Authorization, and Guards

1. Implement immutable Tool Registry.
2. Implement command-profile registry.
3. Implement capability/permission resolution.
4. Implement structured tool-call schemas.
5. Implement server-issued run context.
6. Implement path/workspace guard.
7. Implement symlink policy.
8. Implement budget model.
9. Implement output bounds/redaction utilities.
10. Add unit/threat tests for registry, authorization, paths, schemas, and budgets.
11. Extend role-hardcoding/security structural guards where appropriate.
12. Update PROGRESS.txt.
13. Commit/push Phase 1.

## Phase 2 — Safe Tool Handlers and Audit Persistence

1. Implement bounded repository listing.
2. Implement bounded text-file reading.
3. Implement bounded repository search.
4. Implement safe Git status/diff inspection.
5. Implement structured atomic patch application.
6. Implement named validation-profile runner.
7. Implement timeout and process-tree cleanup.
8. Implement minimal environment and controlled cwd.
9. Implement result truncation/redaction.
10. Implement durable audit persistence or approved existing-model integration.
11. Add migration if required.
12. Emit safe events after durable outcomes.
13. Add threat tests for patches, commands, process handling, output, and audit serialization.
14. Verify migration upgrade and fresh bootstrap.
15. Update PROGRESS.txt.
16. Commit/push Phase 2.

## Phase 3 — Harness and AgentRuntime Integration

1. Implement Harness orchestrator.
2. Implement call validation and authorization before dispatch.
3. Implement call idempotency.
4. Implement per-iteration and per-run budgets.
5. Integrate structured tool requests into AgentRuntime.
6. Implement bounded provider/tool loop.
7. Implement cancellation checks before, during, and after execution.
8. Implement malformed-output bounded retry.
9. Implement structured completion/blocked/failure outcomes.
10. Implement deterministic mock scenarios.
11. Feed diff/validation evidence to the Reviewer stage.
12. Ensure planning stages cannot mutate repository.
13. Add integration tests for success, denial, failure, exhaustion, and cancellation.
14. Update PROGRESS.txt.
15. Commit/push Phase 3.

## Phase 4 — Mission Integration and Safe Observability

1. Integrate Harness into authorized code mission stages.
2. Preserve specification approval gate.
3. Preserve central Employee resolution.
4. Preserve Employee-specific model/skill configuration.
5. Ensure validation failure blocks success.
6. Ensure Reviewer receives actual diff/evidence.
7. Ensure cancellation/failure cleans runtime assignments.
8. Add safe harness summaries to existing mission/task observability.
9. Add minimal dashboard display only if current UI requires it.
10. Wire visible error states.
11. Verify no public arbitrary tool endpoint exists.
12. Run typecheck/build if dashboard changes.
13. Run mock mission E2E with zero keys.
14. Update PROGRESS.txt.
15. Commit/push Phase 4.

## Phase 5 — Security Audit, Regression, and Documentation

1. Run full backend suite.
2. Run frontend tests if changed.
3. Run dashboard typecheck/build.
4. Verify migration from Sprint 15.
5. Verify fresh DB bootstrap and seed.
6. Run deterministic mock Harness E2E.
7. Run existing planning/specification/mission/workspace/widget regressions.
8. Independently audit tool allowlisting.
9. Audit every process invocation for `shell=False`.
10. Audit all path operations and symlink handling.
11. Audit patch atomicity and rollback.
12. Audit timeout/process-tree termination.
13. Audit environment minimization.
14. Audit output bounds and redaction.
15. Audit tool permission intersections.
16. Audit cancellation and stale-callback behavior.
17. Audit event/API/dashboard secret exposure.
18. Audit absence of public arbitrary execution endpoints.
19. Audit WorkflowEngine/AgentRuntime module boundaries.
20. Inspect complete diff for scope leakage.
21. Update:
    - CLAUDE.md
    - PROGRESS.txt
    - README.md if developer/user workflow changed
    - docs/ARCHITECTURE.md
    - docs/DECISIONS.md
    - docs/design/UX_SPEC.md
22. Record residual sandbox limitations honestly.
23. Record Sprint 17 boundaries and deferrals.
24. Commit/push final documentation.
25. Verify clean working tree.
26. Verify local HEAD equals origin/master.

---

## 12. Definition of Done

Sprint 16 is complete only when:

1. Baseline is verified.
2. Canonical Tool Registry is immutable and server-owned.
3. Tools are first-party and allowlisted.
4. Effective permission is an intersection of all required policies.
5. Unknown/missing permissions default to deny.
6. Provider cannot self-grant tools.
7. Every tool call is typed and schema-validated.
8. Run/mission/Employee/stage context is verified.
9. Workspace root is server-selected.
10. Absolute and traversal paths are denied.
11. Symlink escape is denied.
12. Prefix-confusion and non-existent-target escape are denied.
13. Reads/searches are bounded.
14. Writes occur only through structured validated patches.
15. Patches are atomic or fully rolled back.
16. Binary/special-file mutation is denied.
17. Validation uses named server-owned profiles.
18. No arbitrary executable or flags are accepted.
19. Every process uses `shell=False`.
20. Working directory is controlled.
21. Environment is minimized.
22. Tool timeouts terminate process trees.
23. Input/output/file/call/iteration budgets are enforced.
24. Output truncation is explicit.
25. Secret-like data is redacted.
26. Environment and hidden reasoning are not exposed.
27. Calls are idempotent or duplicate-safe.
28. Cancellation prevents further calls.
29. Stale callbacks cannot advance cancelled runs.
30. Validation failure cannot silently mark success.
31. Audit records/events are durable and safe.
32. AgentRuntime supports bounded structured tool calls.
33. Mock mode proves read→patch→validate→complete with zero keys.
34. Denial, exhaustion, malformed output, and failure paths are tested.
35. Reviewer receives actual diff and validation evidence.
36. Specification approval gate remains intact.
37. Central Employee resolver remains intact.
38. Employee model/skill configuration remains active.
39. No generic public tool/shell endpoint exists.
40. No unrestricted network/package-install tool exists.
41. Existing planning/workspace/widget behavior remains functional.
42. Full backend suite passes.
43. Dashboard typecheck/build passes.
44. Migration upgrade and fresh bootstrap pass when applicable.
45. Browser verification is honestly classified.
46. Residual sandbox limitations are documented.
47. No Sprint 17+ self-correction or memory behavior leaked into scope.
48. Documentation matches implementation.
49. Final commits are pushed.
50. Local HEAD equals origin/master.

Do not claim OS-level sandboxing unless independently proven.

---

## 13. Out of Scope

Do not implement:

- unrestricted shell
- arbitrary command execution
- arbitrary executable/flags
- arbitrary network access
- package installation
- deployment tools
- credential-management tools
- destructive filesystem tools
- third-party/user-authored tools
- plugin marketplace
- iframe or browser automation tools
- full container orchestration platform
- production sandbox claims without proof
- Sprint 17 generalized self-correction
- autonomous rollback across runs
- Sprint 18 memory/learning
- multi-user collaboration
- billing
- broad provider expansion
- cloud deployment
- broad Workspace redesign
- widget marketplace

Record future requirements without implementing them.

---

## 14. Final Report

Return one evidence-based report containing:

1. Starting/final/origin SHA and working-tree state
2. Sprint result and checklist/DoD count
3. Commits
4. Repository divergences
5. Threat model and trust boundaries
6. Tool and command-profile registries
7. Permission calculation
8. Workspace/path/symlink protections
9. Patch safety and atomicity
10. Process execution and environment controls
11. Budgets, idempotency, and cancellation
12. Output redaction/truncation
13. Audit persistence and observability
14. AgentRuntime and mission integration
15. Mock Harness E2E
16. Security audit with file/line evidence
17. Migration/bootstrap
18. Verification matrix
19. Starting/ending tests and modified-test classification
20. Existing-feature compatibility
21. Documentation updates
22. Residual risks and low-confidence areas
23. Scope control and Sprint 17 handoff
24. Final state

Begin with Phase 0 and continue through Phase 5 without routine confirmation.
