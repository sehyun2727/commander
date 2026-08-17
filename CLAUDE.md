# CLAUDE.md — Commander

> **Commander is not a program that gives work to AI.**
> **Commander is an operating system for running an AI company.**
>
> When a design question has no obvious answer, the tiebreaker is always: *what would a real company do?*
> Why does the CEO only talk to the PM? Because it's a company.
> Why do Engineers never talk to the CEO? Because it's a company.
> Why does the PM raise approval requests? Because it's a company.
> Why does the Timeline exist? Because it's a company.
> Why does the dashboard look like Render? Because you're operating a company, not chatting.
>
> This philosophy outranks any individual feature.

**Status: V1 released (`v1.0.0`, Sprint 8). V1.1 in development.**

This file describes the project's **stable architecture, invariants, terminology, and working rules**.

Sprint-specific implementation detail belongs in the sprint brief.
Do not turn this file into a copy of a sprint brief.

Sections marked **[V1.1 — not built]** describe intended architecture and must not be implemented without an explicit sprint brief.

---

# 1. What Commander Is

A solo operator becomes the **CEO of an AI software company**.

AI Employees perform the work. The CEO sets direction, reads reports, and makes decisions.

The competitive claim is not simply a better coding agent. It is the **organization layer sitting above replaceable AI workers**:

```text
CEO
 ↓
PM ⇄ CTO
 ↓
Employees
 ↓
Reviewer
 ↓
PM judgment
 ↓
CEO only when required
```

Cursor and Claude Code are tools you drive. They stop when you stop, and the artifact is a diff.

Commander is an organization you govern. It keeps working while you are away, and the artifact is an explained, accountable result.

---

# 2. Organization Model

Two different axes must remain separate.

## 2.1 Decision axis — planning

PM and CTO are peers.

```text
                CEO
                 │
            (one channel)
                 │
        PM  ←── 협의 ──→  CTO
        business        technical
                 │
      Project Specification
                 │
           CEO approval
```

## 2.2 Delegation axis — execution

After approval, work descends through the organization.

```text
        PM
         │
      assigns
         ▼
        CTO
         │
      assigns
         ▼
     Employees
         │
     Reviewer
         │
     PM judgment
         │
 Minor / Major / Critical
         │
    CEO only if Critical
```

## 2.3 Roles vs Employees — the central V1.1 distinction [Sprint 10 ✅ structural separation; Sprint 11 ✅ CTO + hiring]

Role and Employee are different concepts.

Sprint 10 shipped the structural split described below: `RoleSpec` as
frozen, template-owned data; `Employee` (`AgentORM.role_key`) as a CEO-owned
instance; singleton enforcement; idle-first Role → Employee resolution; a
read-only Roles API; and an automated guard against hardcoded role-identity
branches (Rule #16).

Sprint 11 shipped: a first-class `cto` `RoleSpec` (leadership, singleton,
vacant/hireable at founding rather than auto-seeded); a CEO-facing "Hire
Employee" flow (`POST /api/projects/{id}/agents`) that lets the CEO hire
multiple Employees into a worker Role and configure each one's model and
skill template independently, via the same authoritative
`hire_employee`/`update_profile` services used everywhere else; a
database-backed singleton lock (`role_singleton_locks`) that makes
concurrent singleton hiring race-safe; and a canonical, typed,
server-owned skill-template registry (`app/modules/skill_templates/`).
Still pending later sprints: the Backend/Frontend Engineer split and any
role beyond PM/CTO/Engineer/Reviewer, and PM↔CTO planning (Sprint 12).

|              | Owned by | Defines                                                                                | Count             |
| ------------ | -------- | -------------------------------------------------------------------------------------- | ----------------- |
| **Role**     | Template | prompt contract · tools · permissions · workflow position · harness · default behavior | fixed by template |
| **Employee** | CEO      | name · model · personal profile                                                        | unlimited         |

### Leadership roles

Leadership roles are singletons:

```text
PM        → exactly one
CTO       → exactly one
Reviewer  → exactly one
```

They are permanent organizational positions.

### Worker roles

Worker roles are unlimited.

V1.1 ships:

```text
Backend Engineer
Frontend Engineer
```

The architecture must already accommodate future roles as **data**, not as engine branches:

```text
Designer
QA
DevOps
Security
ML Engineer
Data Analyst
Technical Writer
...
```

### Multiple employees per role

A role may hold multiple employees.

```text
Backend Engineer
    ├── Kim  (Claude Sonnet)
    └── Lee  (GPT-5.5)

Frontend Engineer
    └── Park (Gemini)
```

The role describes the position. The Employee is the person occupying it.

The PM ultimately assigns work to a **specific Employee**, not merely to a Role.

### Employee creation

The intended flow is:

```text
Add Employee
    ↓
Select Role
    ↓
Select AI model
    ↓
Select skill template
    ↓
Create
```

Pricing tiers may cap the number of Employees later. The architecture must never assume a fixed employee-count limit.

---

# 3. Product Terminology

UI text must use Commander terminology.

Do not leak engineering terminology into CEO-facing surfaces.

| Internal        | UI                    |
| --------------- | --------------------- |
| Project         | Company               |
| User            | CEO                   |
| Repository      | Workspace             |
| Task            | Mission               |
| Issue           | Risk                  |
| Chat            | Meeting               |
| Agent           | Employee              |
| Agent Group     | Department            |
| Dashboard       | CEO Workspace         |
| Log             | Timeline              |
| Configuration   | Company Settings      |
| Deployment      | Launch                |
| Review          | Audit                 |
| Approval        | CEO Decision          |
| Role definition | Position              |
| Specification   | Project Specification |
| Discussion      | Meeting / 협의          |
| Memory          | Company Knowledge     |
| Budget          | Resource Limit        |
| Stage           | 업무 단계                 |
| Widget          | Widget                |

---

# 4. Hard Architecture Rules

These rules are non-negotiable.

Rules #1–#10 are V1 foundations.
Rules #11 onward define the V1.1 direction.

## #1 — Modules do not import each other's internals

Cross-module communication goes through the approved interface/event boundaries.

The EventBus is the cross-module event boundary.

Do not import another module's private implementation merely because it is convenient.

---

## #2 — Agents do not talk to each other directly

Employees communicate through system-mediated events and workflow state.

Do not create ad-hoc direct Agent-to-Agent calls.

---

## #3 — Significant actions are observable and explainable

Every significant action emits an event.

Every agent action carries a `reason` string.

The system must be able to answer:

```text
Who acted?
What did they do?
Why did they do it?
What happened afterward?
```

---

## #4 — Providers are replaceable

AI providers are never hard-coded into workflow logic.

All model calls go through:

```text
ProviderGateway
    ↓
model_registry
    ↓
provider implementation
```

Logical model references must remain provider-independent.

---

## #5 — Layering must remain explicit

The intended dependency direction is:

```text
Events
  ↓
Domain Modules
  ↓
Workflow
  ↓
API
```

Avoid circular dependencies.

---

## #6 — Mock mode must always work

The entire product must work with:

```text
COMMANDER_PROVIDER=mock
```

and zero API keys.

Mock mode is not a degraded developer-only feature.

It is part of the product's verification model.

Never break mock mode while implementing a real-provider feature.

---

## #7 — Secrets are isolated

Secrets are read only through `SecretsProvider`.

Never:

* log secret values
* return secret values through the API
* echo secrets into prompts
* commit secrets
* store plaintext provider keys in ordinary domain models

---

## #8 — Timeline is one event stream

Timeline is derived from the same event stream used by the system.

`kind: "system" | "conversation"` affects rendering, not storage.

Do not create separate competing sources of timeline truth.

---

## #9 — AI-generated code is never freely executed

AI output is data.

Only trusted template-defined commands may execute.

Those commands execute only inside the sandbox.

AI must never choose an arbitrary command.

Free shell execution is permanently rejected.

---

## #10 — Architecture changes require synchronized documentation

Any architecture change must update:

```text
CLAUDE.md
docs/ARCHITECTURE.md
```

in the same commit.

Desynchronization is an architecture violation.

---

## #11 — The CEO has exactly one conversational counterpart: the PM

There is no CEO route to:

```text
Engineer
CTO
Reviewer
```

The CEO's observation channel is the Timeline and CEO Workspace.

The CEO's intervention channel is a CEO Decision.

All organizational communication reaches the CEO through the PM unless the product explicitly defines a critical decision path.

This is not merely a disabled UI feature.

The route itself should not exist.

---

## #12 — Tools are granted by the Template to a Role

Nobody else grants tools.

Not:

```text
Employee
CEO
Agent output
LLM
Workflow state
```

A Role's tools are a whitelist defined by the company template.

Even autonomous loops must use only template-approved tools.

Free shell execution is permanently forbidden.

The security model is whitelist-based, not blocklist-based.

---

## #13 — Autonomous loops are budgeted

Any potentially looping system must have explicit resource limits.

Examples:

```text
Agent tool loop
PM ↔ CTO discussion
Self-correction
Retry loop
```

Budgets may include:

```text
iterations
tokens
wall time
cost
```

Budget exhaustion is an organizational event, not a silent stop.

The affected Mission becomes blocked with an explicit reason and the CEO is informed.

Never retry forever.

Never silently stop.

---

## #14 — Project Memory is derived from events

There is no second source of truth for company history.

Project Memory is a projection/index over existing events.

If a fact is not represented in the event stream, it cannot become authoritative company memory.

---

## #15 — All data access is account-scoped

The only unauthenticated routes are:

```text
health checks
authentication endpoints
```

Every Company has an owner.

Cross-account access returns:

```text
404
```

rather than:

```text
403
```

because resource existence itself must not be disclosed.

---

## #16 — Roles are data; Employees are instances

No engine, prompt builder, component, or workflow branch may depend on a hardcoded role name.

Forbidden patterns include:

```python
if role == "engineer":
if role_key == "pm":
if role == "reviewer":
```

Behavior must come from the Role definition supplied by the template.

Adding a new Role must not require modifying the workflow engine.

Allowed role-specific constants are limited to the template itself when assembling its own data.

Stage kinds such as:

```text
plan
produce
review
```

are allowed to drive behavior because they represent workflow semantics rather than organizational role identities.

---

## #17 — New CEO-facing capabilities enter through Widgets or Sidebar pages

Do not bolt new capabilities onto the PM conversation surface.

The conversation is the stable center of the CEO experience.

New functionality belongs in:

```text
Widget
Sidebar page
```

unless a later architecture decision explicitly changes this rule.

---

## #18 — CEO actions never fail silently

Every CEO-triggered mutation must have an observable result.

The action must either:

```text
succeed
```

or:

```text
fail with a visible explanation
```

Silent failure is forbidden.

A mutation must not:

* fail without user feedback
* swallow an API error
* leave the UI permanently unchanged without explanation
* rely only on console logging

The trust model of Commander depends on:

> **The CEO decides, therefore the organization moves.**

A button that appears to do nothing is one of the worst possible product failures.

---

# 5. Repository Layout

```text
apps/api/
  FastAPI backend
  Python 3.11+
  async SQLAlchemy
  Postgres default / SQLite tests

  app/core/
    events
    interfaces
    lifecycle
    db
    secrets
    config
    boot_checks

  app/templates/
    software_company.py
    shipped company template
    owns role definitions, pipeline, roster,
    profiles, onboarding data, CheckSpecs

  app/modules/
    projects
    tasks
    approvals
    timeline
    agent_runtime
    agent_profiles
    prompt_builder
    workflow_engine
    event_bus
    provider_gateway
    model_registry
    costs
    reports
    situation
    realtime
    workspace_manager
    sandbox

    [V1.1 adds as needed]
    auth
    roles
    employees
    specifications
    memory
    widgets

  alembic/
    migration environment
    alembic/versions/

  tests/

apps/dashboard/
  Next.js App Router
  TypeScript
  Tailwind
  TanStack Query

packages/event-schemas/ts/
  generated TypeScript event contracts
  DO NOT hand-edit

scripts/
  generate_ts_schemas.py
  seed.py
  verify_real_llm.py

docs/
  ARCHITECTURE.md
  DECISIONS.md
  backend specifications

docs/design/
  UX_SPEC.md
  frontend experience source of truth

docs/prompts/
  sprint briefs
```

---

# 6. Repository Documentation Is the Source of Project Context

Claude Code does not need the entire project re-explained inside every sprint prompt.

The repository itself is the persistent context.

Before implementing a sprint, inspect the documents relevant to that sprint.

At minimum:

```text
CLAUDE.md
docs/ARCHITECTURE.md
docs/DECISIONS.md
docs/design/UX_SPEC.md
PROGRESS.txt
```

Then inspect the code paths named or implied by the sprint brief.

Do not ask the CEO/developer to paste repository documents into the prompt when those documents already exist in the repository.

The sprint brief should describe:

```text
what to change
why it matters
constraints
definition of done
scope boundaries
```

The repository documents describe:

```text
what already exists
why previous decisions were made
how the current architecture works
```

Do not duplicate the same information unnecessarily.

This keeps implementation prompts compact without reducing architectural context.

---

# 7. Working Model for Sprint Execution

Commander is intentionally developed using **large autonomous sprint runs**.

The expected working pattern is:

```text
One large sprint brief
        ↓
Claude Code reads the repository context
        ↓
Claude implements autonomously
        ↓
Tests / build / browser verification
        ↓
Commits + push
        ↓
Human review
        ↓
Next sprint brief
```

A sprint brief may run for a long session.

Do **not** artificially split a sprint into many tiny prompt-response cycles unless the brief itself requires an independent checkpoint.

## 7.1 Do not stop for routine confirmation

When a sprint brief says to work autonomously:

* do not stop after every phase
* do not ask whether to continue
* do not ask permission for routine refactors
* do not wait for confirmation when the correct engineering choice is reasonably clear

When ambiguity exists:

1. choose the most reasonable engineering decision
2. implement it
3. record the judgment in `docs/DECISIONS.md`
4. continue

Only stop when:

* the sprint is complete, or
* a genuine hard blocker makes further progress impossible.

---

## 7.2 Large prompts are intentional

A large sprint brief is not a reason to restate the entire project.

The preferred pattern is:

```text
Sprint brief
  = mission + constraints + required outcomes
```

not:

```text
Sprint brief
  = mission + copied repository documentation + copied architecture
```

Use the repository as the persistent knowledge base.

---

## 7.3 Work for the full sprint, not just the first phase

If the sprint brief contains:

```text
Phase 0
Phase 1
Phase 2
Phase 3
Phase 4
Phase 5
```

and the brief author has explicitly requested autonomous execution, continue through the phases.

Do not treat each phase as a mandatory conversation boundary.

Use commits and `PROGRESS.txt` as internal checkpoints.

---

## 7.4 Keep changes reviewable

Although a sprint may run as one long autonomous session, implementation must remain structured.

Use:

```text
phase-sized commits
clear commit messages
PROGRESS.txt updates
targeted tests
```

This preserves reviewability without requiring many interactive prompts.

---

## 7.5 Verify before reporting completion

A green unit-test suite is not automatically proof of product behavior.

When the sprint brief requires UI or end-to-end behavior:

```text
run the application
exercise the relevant path
observe the result
```

Do not claim browser verification when only a test or curl command was run.

---

# 8. Commands

```bash
make install
make db-up
make db-down
make db-upgrade
make db-downgrade
make seed
make dev
make demo
make test
make verify-llm
make export-users
```

Detailed meanings:

```text
make install
  API + dashboard dependencies

make db-up
  start Postgres and wait for health

make db-upgrade
  apply Alembic migrations to head

make db-downgrade
  roll back one migration

make seed
  start DB, upgrade schema, reset DB,
  create demo Company "Acme AI"

make dev
  DB + API :8000 + dashboard :3000

make demo
  seed + dev

make test
  pytest + dashboard typecheck + dashboard build

make verify-llm
  one real Anthropic Mission against a throwaway DB

make export-users
  export CEO accounts to CSV using password hashes only
```

After event schema changes:

```bash
python scripts/generate_ts_schemas.py
```

Password reset:

```bash
python scripts/reset_password.py <email> <new-password>
```

---

# 9. Engineering Conventions

## 9.1 Events

Use a single Pydantic v2 `Event` envelope.

Each event type requires:

```text
enum/type registration
payload model
generated TypeScript contract
```

Call:

```python
build_event()
```

rather than constructing ad-hoc event dictionaries.

After event schema changes:

```bash
python scripts/generate_ts_schemas.py
```

Never hand-edit generated event types.

---

## 9.2 State machines

`core/lifecycle/` owns Agent and Task state transitions.

Never directly mutate state fields when a transition API exists.

Use:

```text
transition()
```

and preserve legal transition rules.

---

## 9.3 Database sessions

Each workflow step opens its own DB session.

Never hold an ORM object across an `await` on the provider.

Pass immutable snapshots between stages.

---

## 9.4 Frontend

Use TanStack Query for server state.

SSE events are deduplicated by:

```text
event.id
```

Then invalidate/refetch the appropriate queries.

Use generated event types.

Never redeclare event contracts manually.

Every mutation must surface failure visibly.

---

## 9.5 Reviewer verdicts

Reviewer output ends with:

```text
**Verdict:** ...
```

Parsing is provider-agnostic.

Workflow logic must not branch on provider-specific response formatting.

---

## 9.6 Code missions

There is one real Git repository per Company.

Each Mission gets:

```text
mission/{task_id[:8]}
```

Engineer output is parsed from:

```text
===== FILE: path =====
```

blocks.

Zero valid file blocks falls back to a document Mission instead of silently failing.

Only trusted template `CheckSpec` commands execute.

Read the Security Model in `docs/ARCHITECTURE.md` before modifying sandbox behavior.

---

## 9.7 Commits

Use conventional commit style:

```text
feat(scope): ...
fix(scope): ...
refactor(scope): ...
docs: ...
test(scope): ...
chore: ...
```

A non-obvious architectural judgment should receive a `docs/DECISIONS.md` entry.

---

# 10. Current Status — V1 As-Built

V1 shipped as:

```text
v1.0.0
```

and the V1 pipeline is functional.

Current V1 capabilities include:

* Company CRUD
* founding roster
* PM / Engineer / Reviewer
* Agent profiles
* Timeline events
* starter Missions
* PM → Engineer → Reviewer pipeline
* background workflow execution
* provider retry/backoff
* Git workspace
* mission branches
* real diffs
* CEO approval/merge
* sandbox checks
* token/cost tracking
* model resolution
* Postgres
* Alembic
* health endpoints
* auth foundation
* SSE reconnect behavior
* mock mode
* Reports
* Workspace browser
* Employees page
* company settings
* Timeline filters and pagination

At the V1 baseline:

```text
157 tests
4 skipped
```

---

# 11. V1 Deliberate Limits

V1 intentionally remains limited.

## 11.1 Engineer is one-shot

The Engineer:

```text
does not inspect the existing repository
does not iterate
does not self-correct
```

Mission #2 does not automatically learn from Mission #1.

This remains true until the Sprint 16 brief explicitly changes it.

---

## 11.2 CEO input is the development input

V1 has no complete requirements-discovery layer.

Structured specification is introduced later.

---

## 11.3 CEO remains inside the pipeline

V1 still depends heavily on CEO decisions.

The organization is not yet fully autonomous.

---

## 11.4 No project memory

Historical learning does not yet exist.

---

# 12. V1.1 Roadmap

V1.1 is built through explicit sprint briefs.

| Phase | Sprint | Deliverable                                           |
| ----- | -----: | ----------------------------------------------------- |
| A     |    9 ✅ | Reliability + auth                                    |
| B     |   10 ✅ | Role / Employee separation                            |
| B     |   11 ✅ | CTO + multi-employee + hiring                         |
| C     |     12 | PM↔CTO planning + Project Specification               |
| D     |     13 | CEO↔PM conversation + PM reports + decision authority |
| D     |     14 | CEO Workspace UI shell                                |
| D     |     15 | Widget system                                         |
| E     |     16 | Agent Harness                                         |
| E     |     17 | Self-correction                                       |
| F     |     18 | Project Memory + Sprint Learning                      |
| G     |     19 | Mission Tree + remaining widgets                      |
| H     |     20 | V1.1 release                                          |

V1.1 is complete only when the architecture, product surface, and real LLM flow all work together.

---

# 13. V1 / V1.1 Boundary

Do not blur sprint boundaries.

Everything already shipped in V1 remains stable unless an explicit sprint brief changes it.

Everything marked V1.1 must wait for its sprint.

Do not implement future roadmap items "while you're in there."

For example:

```text
Sprint 10
→ Role / Employee structure

NOT:
→ CTO
→ hiring
→ autonomous tool loop
→ memory
```

Those belong to later sprints.

An implementation may prepare extension points for future work, but must not quietly implement the future feature itself.

---

# 14. V1.1 Out of Scope

Unless a later roadmap revision explicitly changes this:

* second company template shipment
* multi-user collaboration on one Company
* hosting/cloud deployment
* providers beyond Anthropic + mock
* template marketplace
* parallel Backend/Frontend execution
* implementation of Designer / QA / DevOps / Security roles

The architecture may support these things.

V1.1 does not ship them.

---

# 15. Known Accepted Tradeoffs

Do not "fix" these merely because they are theoretically improvable:

```text
plaintext secrets
in-process EventBus
single worker assumptions
inline EventBus subscriber execution
Python-side conversation filtering
no connection pooling
no read replicas
no backup tooling
single local Postgres assumptions
fabricated-but-labeled mock Payroll figures
```

Read `docs/DECISIONS.md` before changing any accepted tradeoff.

---

# 16. Working Style

## 16.1 Autonomous by default

When a sprint brief says to work autonomously:

```text
read → decide → implement → verify → continue
```

Do not ask routine questions.

---

## 16.2 Spec wins over legacy code

If existing code conflicts with the approved sprint architecture:

```text
refactor toward the spec
```

Do not create unnecessary compatibility layers solely to avoid touching legacy code.

---

## 16.3 Prefer boring technology

Prefer:

```text
simple
explicit
testable
reliable
```

over clever abstractions.

If a library fights the implementation for a sustained period and a simpler solution exists, replace it.

---

## 16.4 Do not duplicate repository knowledge inside prompts

Sprint briefs should reference files rather than copy large portions of them.

For example:

Good:

```text
Read:
CLAUDE.md
docs/ARCHITECTURE.md §4.1
docs/DECISIONS.md
```

Bad:

```text
paste the entire contents of those documents
```

This reduces context duplication and leaves the repository as the durable source of truth.

---

## 16.5 Large sprint brief, one long implementation run

The intended development rhythm is:

```text
GPT / human
    ↓
large sprint brief
    ↓
Claude Code
    ↓
long autonomous implementation run
    ↓
verification
    ↓
human / GPT review
    ↓
next sprint
```

This is intentional.

Do not force the developer into dozens of tiny implementation prompts.

Claude Code should be capable of reading repository context and carrying the sprint through independently.

---

## 16.6 Use progress and commits as internal checkpoints

Long autonomous work must remain observable through:

```text
PROGRESS.txt
git commits
tests
build results
browser verification
```

Update `PROGRESS.txt` per completed item.

Do not batch all progress updates at the end.

---

## 16.7 Never fake verification

These are different claims:

```text
"unit test passed"
"API endpoint passed"
"browser behavior verified"
"real LLM E2E passed"
```

Report the strongest claim that was actually observed.

Do not call something browser-verified if only curl was used.

Do not call something real-LLM verified if mock mode was used.

---

# 17. Final Sprint Completion Rule

A sprint is not complete merely because the implementation exists.

Completion requires, as applicable:

```text
tests
typecheck
build
runtime verification
browser verification
documentation
PROGRESS.txt
commit
push
remote HEAD confirmation
```

Every sprint's final implementation commit must be pushed.

The sprint is complete only when:

```text
remote HEAD == intended final commit
```

and the completion report truthfully states:

```text
passed
failed
unverified
```

for the relevant Definition of Done items.

---

# 18. What Not to Do

Never:

* invent architecture without checking repository documentation
* duplicate existing project knowledge unnecessarily in prompts
* silently broaden sprint scope
* add future roadmap features early
* bypass EventBus boundaries
* bypass ProviderGateway
* grant tools outside template data
* execute arbitrary AI-generated shell commands
* silently swallow mutation errors
* claim verification that was not performed
* rewrite large portions of the system merely because a cleaner theoretical design exists

When uncertain:

```text
inspect
decide
record the decision
continue
```

The objective is not maximum code.

The objective is a coherent AI company operating system.

---

# 19. Final Principle

Commander should feel less like:

```text
"Ask an AI to code."
```

and more like:

```text
"Run a company whose employees happen to be AI."
```

Every architecture decision, workflow, UI decision, event, and implementation should move toward that distinction.

**The system is the company.
The AI models are replaceable workers.
The CEO governs the organization.**
