# Sprint 19 — V1.1 Shipping: Verification, Minimum Observability, Release

Execute this sprint autonomously from Phase 0 through Phase 4.

Expected baseline:
- local HEAD: dbb299b
- origin/master: dbb299b
- backend baseline: 512 passed / 6 skipped
  (2 of the 6 skips are Windows symlink-privilege skips in
  `test_agent_harness_guards.py` — expected on Windows dev, absent on Linux)
- dashboard typecheck/build: PASS (19 routes compile)
- migration head: `c2a7e1f4b6d3_memory_records`
- mock E2E with zero provider keys: PASS
- Sprint 18 shipped: Project Memory (deterministic, PM-triggered recall)
- browser-rendered interaction verification: UNVERIFIED (Sprints 16–18 introduced no CEO-facing UI)

Repository and git state are authoritative. Verify every baseline claim first.

Follow the current CLAUDE.md, architecture, decisions, UX specification, security constraints, progress discipline, verification standards, and reporting format.

Do not stop for routine confirmation. Stop only for a hard blocker, destructive ambiguity, security/cost exposure, or irreconcilable architectural conflict.

**This sprint's outcome is a git tag `v1.1.0`. Do not tag until every item in §12 (Definition of Shipping) is verifiably true.**

---

## 1. Goal

**V1.1 has been under development since Sprint 9. Sprint 19 verifies the whole thing, adds the minimum observability that release-grade software honestly needs, writes the deployment story a stranger can follow, and cuts `v1.1.0`.**

At the end of Sprint 19:

1. A third first-party `ProviderGateway` implementation exists — `OpenRouterProvider` — proving Rule #4 (providers are replaceable) in production, not only in theory.
2. `COMMANDER_PROVIDER` accepts `mock` | `anthropic` | `openrouter`; the existing three-tier model resolution (Employee override → CEO per-role override → registry default) works uniformly across all three.
3. Real-LLM full E2E has been executed and recorded at least twice: once against Anthropic direct (Claude), once against OpenRouter routing a free-tier model (smoke). Free-tier model quality variance is documented separately from release-blocking evidence.
4. Every HTTP request gets a server-issued correlation ID; every background mission's log lines carry `task_id`; every agent log line carries `agent_id`; logs are structured as JSON one-liners with a single formatter.
5. Load smoke evidence for 4 concrete scenarios (§4.8) is recorded in the release notes as the documented safe operating envelope.
6. Fresh-box deployment has been walked through end-to-end on a clean environment; `docs/DEPLOYMENT.md` is what the operator followed.
7. `v1.0 → v1.1` upgrade path is documented — especially the Sprint 9 auth schema jump and Sprints 10–18 migration chain.
8. Independent whole-system security audit (one pass, not per-module) has been run by a dedicated agent and every finding resolved or explicitly accepted.
9. Every accepted tradeoff, every deferred category, every known limitation is enumerated in one place — `docs/KNOWN_ISSUES.md` — so no future operator or CTO discovers a "hidden" constraint.
10. `CHANGELOG.md` v1.1.0 entry, `CLAUDE.md` roadmap row 19 ✅ and "V1.1 released", `docs/ARCHITECTURE.md` deployment section, `FOR_CTO.md` §18d handover addendum, and `docs/DECISIONS.md` #249+ close-out all synchronized in the same commits as the code.
11. Local HEAD equals origin/master; `git tag v1.1.0` created and pushed.
12. Every V1 feature and every Sprint 9–18 feature still works — full backend suite green, dashboard typecheck/build green, mock E2E green.

This sprint does **not** add new modules, new CEO-facing UI, production Docker Compose, backup automation, rate limiting, metrics collection infrastructure, log aggregation infrastructure, HTTPS terminator configuration, load testing frameworks (k6/JMeter/Locust), a second company template, cross-Company federation, or any feature listed as V1.2 candidate. It does not modify accepted tradeoffs in CLAUDE.md §15 or Sprints 16/17/18's out-of-scope declarations.

---

## 2. Security Model

Sprint 16–18's security model applies unchanged. Sprint 19 adds:

- **`OpenRouterProvider` reads its API key only through `SecretsProvider`.** No direct `os.environ` read, no direct `settings.openrouter_api_key` access outside the provider itself. Same choke point as `ANTHROPIC_API_KEY` (Rule #7).
- **Correlation IDs never contain user-controllable content.** The middleware generates a server-side UUID; it never trusts an incoming header (`X-Request-Id` etc.), which would let a client forge log correlation.
- **Structured log lines never emit secrets, session tokens, cookies, API keys, or full request bodies.** A single formatter enforces this; any field added later must go through the same formatter.
- **Free-tier LLM E2E is a smoke test, not a security signal.** Free-model output quality varies wildly; any "it passed" from a free model is evidence of provider wiring, not of the shipping product's operational reliability under adversarial input.
- **Deployment documentation must not accidentally leak dev credentials into the operator's mental model.** The `.env.production.example` template is example-only; the operator generates real secrets locally, never copies from a committed file.

Everything else — tool authorization, path safety, patch atomicity, process isolation, output redaction, cancellation, budgets, audit persistence, memory record boundedness — is untouched.

---

## 3. Required Repository Inspection

Before changing code, inspect at minimum:

- CLAUDE.md — especially §7 (Working Model), §15 (Accepted Tradeoffs), §17 (Final Sprint Completion Rule)
- PROGRESS.txt (currently "SPRINT 18 DONE. Now working on: nothing -- awaiting Sprint 19 brief")
- README.md — status paragraph is the current shipping story (Sprint 15 flavor); Sprint 19 rewrites it
- FOR_CTO.md — the current CTO handover with all Sprint 16/17/18 handoffs
- docs/ARCHITECTURE.md — especially §5 (Memory), §6 (module map), §7 (Security), §9 (Accepted Tradeoffs)
- docs/DECISIONS.md #233–#248 (Sprints 16–18 as-shipped)
- docs/design/UX_SPEC.md
- git history through dbb299b (all V1.1 sprint close-outs)
- `apps/api/app/modules/provider_gateway/anthropic_provider.py` — the existing Anthropic implementation shape
- `apps/api/app/modules/provider_gateway/mock_provider.py` — how a second provider is structured
- `apps/api/app/modules/provider_gateway/gateway.py` — `RoutedProviderGateway` + `build_gateway` factory pattern
- `apps/api/app/modules/model_registry/registry.py` — per-provider model maps
- `apps/api/app/core/config.py` — `settings.commander_provider` literal type
- `apps/api/app/core/secrets.py` — `SecretsProvider` + `_ENV_DEFAULTS` extension pattern
- `apps/api/app/main.py` — where singletons/middleware wire in, where lifespan runs
- `apps/api/app/deps.py` — how per-request state is threaded
- `apps/api/app/core/events/base.py` — Event envelope (does not need a correlation_id field; contextvar approach preserves the envelope shape)
- `apps/api/app/modules/workflow_engine/engine.py` — how background workflows relate to originating requests (they don't share the request scope; correlation ID design must account for this)
- `apps/api/app/modules/event_bus/bus.py` — how events publish and fan out (subscribers run inline in `publish`)
- `apps/api/app/core/boot_checks.py` — existing startup validation to extend for provider config
- `apps/api/tests/conftest.py` — the `Harness` fixture shape (isolate any new provider tests behind fixtures like existing MockProvider tests do)
- `scripts/verify_real_llm.py` — the existing one-off real-LLM verification; Sprint 19 extends this
- `Makefile` — existing `make verify-llm` target
- `docker-compose.yml` — current dev-only compose (Postgres); Sprint 19 does NOT extend this file
- `.env.example` — template shape (Sprint 19 extends)
- `.gitignore` — confirms `.env` and `.env.*` are ignored (dev creds never committed)
- `apps/api/alembic/versions/` — migration chain (9 files as of Sprint 18)
- `apps/api/tests/test_health.py` — existing health-check tests
- `apps/api/tests/test_reliability.py` — orphan recovery / cancel / budget guard tests (Sprint 9)
- `docs/backend/workflow/*` — older per-file design notes (some are stale — treat as historical)

Search specifically for:

- every existing `ProviderGateway` subclass — Sprint 19 adds one more, matches their shape
- every `logging.getLogger(...)` call — Sprint 19 unifies formatter, does NOT change logger names
- every `os.environ` read outside `config.py`/`secrets.py` (should be zero; audit confirms)
- every `settings.anthropic_api_key` read outside `secrets.py` (should be zero; the OpenRouter equivalent must follow the same rule)
- every place a `task_id` / `agent_id` / `project_id` is available in scope — Sprint 19's log formatter reads these from contextvars, so the workflow engine must set them at the right boundary points

Document existing execution paths before wrapping or extending them.

---

## 4. Approved Decisions

### 4.1 Scope — verification + minimum observability + release

Sprint 19 is **verification-heavy plus a small, targeted set of code additions.** The additions are:

1. `OpenRouterProvider` and its model-registry entries.
2. A per-request correlation ID middleware + contextvar wiring.
3. A single structured JSON log formatter.
4. Extended `.env.example` and a new `.env.production.example` template.

Everything else in Sprint 19 is verification, documentation, and release. No new modules, no new CEO-facing UI, no new API endpoints, no new dashboard code beyond regenerated TS event schemas (there are no new events this sprint, so even that may be unnecessary).

### 4.2 `OpenRouterProvider` — first-party, follows existing structure

New file `apps/api/app/modules/provider_gateway/openrouter_provider.py`. Concretely:

- Implements `ProviderGateway` (does NOT subclass `AnthropicProvider` — OpenRouter's non-Anthropic model routing uses OpenAI-compatible `/v1/chat/completions`, not Anthropic-compatible `/v1/messages`; wrapping `AnthropicProvider` would force a wire-format mismatch).
- Uses OpenAI-compatible endpoint: `https://openrouter.ai/api/v1/chat/completions` (works for every model OpenRouter routes, including Claude, Llama, Qwen, Gemini variants).
- Reads `OPENROUTER_API_KEY` through `SecretsProvider` (same discipline as `ANTHROPIC_API_KEY`).
- Sends `Authorization: Bearer <key>` header (OpenAI convention, not Anthropic's `x-api-key`).
- Sends OpenRouter-recommended optional headers `HTTP-Referer` and `X-Title` (values: `https://github.com/anthropics/commander` and `Commander` — deterministic, no client input).
- Translates request:
  - Commander's `(system, messages)` → OpenAI's `messages` (prepends a system message).
  - Commander's `tools=[{name, description, input_schema}]` → OpenAI's `tools=[{"type": "function", "function": {name, description, parameters}}]`.
- Translates response:
  - OpenAI `choices[0].message.content` → Commander `CompletionResult.text`.
  - OpenAI `choices[0].message.tool_calls[]` → Commander `tuple[ToolCallData, ...]`.
  - OpenAI `choices[0].finish_reason` (`"stop"` / `"tool_calls"` / etc.) → Commander `stop_reason`.
- Supports `stream()` for text-only streaming (mission `_run_role` path uses this). Tool-loop turns use non-streaming `complete()` (Sprint 16 §7 unchanged).
- Retry-with-backoff for 429/5xx is handled by the existing `RoutedProviderGateway` wrapper — the underlying `OpenRouterProvider` only raises; the wrapper decides retry.

### 4.3 Model registry extension

`apps/api/app/modules/model_registry/registry.py` gains an `openrouter` map alongside `mock` and `anthropic`. Each logical ref (`planner-default`, `builder-default`, `reviewer-default`, `advisor-default`) maps to a concrete OpenRouter model id.

**Default map choice:** pick free-tier OpenRouter model ids at Phase 0 implementation time. Free-tier availability changes; the choice must be a Phase 0 decision recorded in DECISIONS.md, not baked into the brief. Any Sprint 19-time free tier that OpenRouter offers with reasonable tool-use support is acceptable. If OpenRouter's free tier at implementation time has NO tool-use-capable model, default the map to a low-cost paid model (e.g. `anthropic/claude-haiku-4.5-...` or the OpenRouter equivalent) and document the choice.

CEO can override any role's model per Company via the existing per-role override path (Sprint 4.5), and any Employee can override its own model via `profile.model_ref` (Sprint 4.5). Sprint 19 does not add a new override mechanism; it only extends the registry.

`build_gateway(provider_name, ...)` in `provider_gateway/gateway.py` grows one more branch: `provider_name == "openrouter"` returns `RoutedProviderGateway(provider_name, OpenRouterProvider(secrets), ...)`.

### 4.4 `COMMANDER_PROVIDER` union extension

`apps/api/app/core/config.py::settings.commander_provider` is currently `Literal["mock", "anthropic"]`. Extend to `Literal["mock", "anthropic", "openrouter"]`. `boot_checks.validate_boot_config` gains a check: when `commander_provider == "openrouter"`, `OPENROUTER_API_KEY` must resolve non-empty via `SecretsProvider` (or through `settings_kv` Company Settings override), else fail-fast startup with a legible error — same shape as the existing Anthropic check.

### 4.5 Free-tier LLM full E2E — smoke test, quality issues recorded separately

**The user has explicitly approved:** attempt a full PM → CTO → Mission → Engineer → Validation → Reviewer E2E against an OpenRouter free-tier model. This is the primary provider-integration proof and must be attempted.

**Design constraints for the free-model E2E:**

1. Run the smoke test in the same order a first-time CEO would use Commander: found Company → hire CTO → start a Specification (PM↔CTO planning) → approve → mission executes → CEO decision. Do not skip stages.
2. Attempt at least one code Mission (harness path with `tool_loop`) AND at least one document Mission (one-shot path). If the free model cannot reliably emit `tool_use` blocks, the code Mission may fail — that is expected and does not block release.
3. Every failure of the free-model E2E is diagnosed to a specific cause (weak JSON output on planning turn, missing `tool_use` on harness, missing `**Verdict:**` line on Reviewer) and recorded in `docs/KNOWN_ISSUES.md` under "Provider variance — free-tier models".
4. Success of the smoke test proves the provider wiring works. It does NOT prove any specific free model is production-quality. `docs/KNOWN_ISSUES.md` states this explicitly.
5. `make verify-llm --provider=openrouter` (see §4.7) is the reproducer.

**Release evidence is Anthropic-direct + OpenRouter-routing-to-Claude, not free-tier E2E.** See §4.6.

### 4.6 Anthropic-direct + Claude-via-OpenRouter — release-quality evidence

For `v1.1.0` release evidence (the "does the shipping product actually work with a serious model" claim), do at least two real-LLM full E2E runs:

- **Anthropic direct.** `COMMANDER_PROVIDER=anthropic`, real `ANTHROPIC_API_KEY`. One full mission cycle: Specification → CEO approval → Mission → Reviewer verdict → CEO Decision.
- **Claude via OpenRouter.** `COMMANDER_PROVIDER=openrouter`, real `OPENROUTER_API_KEY`, model registry temporarily overridden (via per-role setting or in-process fixture) to route to `anthropic/claude-sonnet-4.5` (or the current Sonnet equivalent OpenRouter routes). Same full mission cycle.

Cost budget: under $1 total for all real-LLM runs across Sprint 19. If a single run exceeds $0.50, stop and diagnose — something is wrong.

Both runs must produce evidence in the final report (turn count, token spend, elapsed wall time, final Mission state).

### 4.7 `make verify-llm` extension

`scripts/verify_real_llm.py` currently does one Anthropic-direct real Mission against a throwaway database. Sprint 19 extends it to accept `--provider` (default `anthropic`, accepts `anthropic|openrouter`) and, when `openrouter`, requires `OPENROUTER_API_KEY`.

`Makefile` `make verify-llm` remains the default Anthropic run. Add `make verify-llm-openrouter` as a second target, or use the make variable pass-through convention already in the Makefile — pick whichever matches existing style.

The script's throwaway-database, one-mission-only, real-diff shape is preserved. It is NOT a load test.

### 4.8 Load smoke — four scenarios, no framework

Add `scripts/load_smoke.py` — a plain asyncio Python script (no k6, no JMeter, no Locust, no new dependency). It runs against a local `make dev` instance (or a temporary throwaway process) with `COMMANDER_PROVIDER=mock` and records timing/query-count/memory evidence for these four scenarios:

1. **1 Company × 10 sequential Missions.** Assert every mission completes; assert 10th mission's wall time is within 1.5× the 1st's; assert Python RSS growth < 100 MB over the run.
2. **3 Companies × 3 concurrent Missions each.** Assert every mission reaches `pending_approval` without deadlock; assert SSE stream for each Company remains connected throughout.
3. **Hot-path query counts.** Instrument `GET /api/projects/{id}/workspace/overview`, `GET /api/projects/{id}/situation`, and one harness dispatch (`dispatch_tool_call` for a single `read_file`). Assert query count is constant with respect to Company/Mission scale for the first two; assert harness dispatch is bounded (small constant number of writes per call: 1 audit row + optionally 1 event row).
4. **Memory recall against 1,000 records.** Populate `memory_records` via test fixture; assert `recall(project_id, request)` returns in under 200 ms wall-clock on a fresh (uncached) DB connection.

Recorded evidence is a short markdown table in the final report AND a paragraph in `CHANGELOG.md`'s "Verified operating envelope" note.

**These four scenarios are the entire load-testing scope for Sprint 19.** Do not add more, do not increase scale, do not introduce framework tooling. If a scenario reveals a genuine bug (e.g. an N+1 in `workspace/overview`), fix it inside Sprint 19; if it reveals only a scale limit, record the limit in `docs/KNOWN_ISSUES.md` and move on.

### 4.9 Correlation ID + structured logging — minimum observability

**Two independent ID scopes, not one unified correlation ID.** Async background workflows outlive the HTTP request that spawned them, so trying to thread one correlation ID from request through mission is confusing. Instead:

**HTTP request scope:**
- FastAPI middleware assigns each request a server-side UUID (`request_id`).
- Middleware sets `request_id` in a `contextvars.ContextVar`.
- The custom log formatter reads the contextvar and includes `request_id` on every log line emitted during request handling.
- Middleware NEVER trusts an incoming `X-Request-Id` header (§2 security note).
- Middleware returns `X-Request-Id: <uuid>` in the response, so an operator can correlate an HTTP response to server logs.

**Background mission scope:**
- `CommanderWorkflowEngine._spawn(task_id, ...)` sets `task_id` in a separate contextvar for the duration of the pipeline.
- `_run_role` / `_run_engineer_tool_loop` set `agent_id` in a third contextvar around the Employee's activity.
- The formatter includes all set contextvars (`request_id`, `task_id`, `agent_id`, `project_id` when known) on each log line.

**Structured logging format:**
- One custom `logging.Formatter` subclass in `apps/api/app/core/logging.py` (new file, ~40 lines).
- Emits one JSON object per log record, keys: `ts` (ISO-8601), `level`, `logger`, `msg`, plus set contextvars.
- Never emits `exc_info` raw — uses `logging.Formatter.formatException` (which the formatter still calls for tracebacks) and embeds the traceback as a single string field.
- Never emits fields whose names match secret-shaped keys (blocklist: `password`, `token`, `key`, `secret`, `authorization`, `cookie`). If a logger call somehow passes one, the formatter redacts it.
- Wired in `main.py::lifespan` via `logging.config.dictConfig` (or equivalent) — replaces the default formatter for the root logger. Existing `logging.getLogger("commander.*")` calls need no change.

**Not adding a logging library dependency.** No `python-json-logger`, no `structlog`. The formatter is code Commander owns.

### 4.10 No new UI, no new API endpoints

Same discipline as Sprint 16/17/18:

- No new widget in `workspace_widgets/registry.py`.
- No new `MissionDetail.tsx` field, no `SpecificationDetail.tsx` field.
- No new page or route in `apps/dashboard/app/`.
- No new HTTP endpoint on the backend.
- The only allowed frontend change is regeneration of TS event schemas (`python scripts/generate_ts_schemas.py`) if events change — but Sprint 19 adds NO new event types, so this may not even be needed. If it is needed for other reasons (e.g. `X-Request-Id` header type addition to `lib/api.ts`), keep the change to type definitions only.

### 4.11 Documentation deliverables

New / updated documents produced in Sprint 19:

- **`docs/DEPLOYMENT.md`** (new). Structure:
  1. Prerequisites (OS: Linux/macOS/WSL, Python 3.11+, Node.js 20+, pnpm, Docker Desktop or Docker Engine, git).
  2. First deployment walkthrough (git clone → `make install` → `make db-up` → `make db-upgrade` → `make seed` (optional, demo) → `make dev` OR the production run recipe).
  3. Production run recipe (a `nohup uvicorn ... &` or systemd-unit-example approach; no full ops stack).
  4. `.env.production.example` template (see below).
  5. Optional HTTPS termination via nginx reverse proxy — a small example config, marked "optional, not required for v1.1.0 to function."
  6. Backup: `pg_dump` for Postgres + `tar` for `./workspaces` directory. Restore instructions.
  7. Upgrade from v1.0.0 (or from any pre-Sprint-19 revision): `git pull` → `make db-upgrade` → restart. Special note on Sprint 9 auth schema — v1.0.0 has no `users`/`sessions` table; migration `fa793dce62cb_accounts_and_sessions` adds them. Existing pre-auth data has no `owner_id` — document the manual attribution step (`scripts/reset_password.py` or a one-line SQL to assign existing Companies to the CEO's newly-created account).
  8. Link to `docs/KNOWN_ISSUES.md` for operational limits.

- **`.env.production.example`** (new). Same shape as `.env.example` but with production-oriented comments (never `mock` provider in prod, always set `COMMANDER_COOKIE_SECURE=true`, use a strong `POSTGRES_PASSWORD`, etc.). Committed to the repo as an example; the operator's real `.env` remains gitignored.

- **`docs/KNOWN_ISSUES.md`** (new). One consolidated list of every accepted tradeoff, deferred category, and operational limit. Structure:
  - Accepted tradeoffs (CLAUDE.md §15 verbatim, with brief context per item)
  - Sprint 15 deferrals (widget-related)
  - Sprint 16 deferrals (harness scope)
  - Sprint 17 deferrals (self-correction scope)
  - Sprint 18 deferrals (memory scope — architecture_decisions, coding_conventions, RAG, cross-Company, Employee memory tool, CEO-facing UI)
  - Sprint 19 verified operating envelope (from §4.8's load smoke)
  - Provider variance notes (free-tier model quality caveats from §4.5)
  - v1.0 → v1.1 upgrade caveats

- **`CHANGELOG.md`** (new). v1.1.0 entry summarizing every Sprint 9–19 landing. One-line-per-feature bullet list per Sprint. Also lists breaking changes (Sprint 10 `AgentORM.role_key` rename, Sprint 9 auth schema addition).

- **`CLAUDE.md`** roadmap: mark `19 ✅ V1.1 released`. Update the status line at the top to reflect v1.1.0 shipped.

- **`docs/ARCHITECTURE.md`**: add a new §11 "Deployment" that summarizes what `docs/DEPLOYMENT.md` covers in one paragraph. Update §9 (Accepted Tradeoffs) if any tradeoff resolved during Sprint 19 (it should not; §9 remains the source of truth for Rule #15 items).

- **`docs/DECISIONS.md`** #249+: the Sprint 19 close-out entry (baseline verification, OpenRouter design, correlation ID design, load smoke findings, real-LLM E2E findings, V1.2 lightweight candidate list).

- **`FOR_CTO.md`**: new §18d Sprint 19 handover addendum + §12 additions (Sprint 19 decisions) + §7 additions (OpenRouterProvider, logging) + §14 additions (new files) + §19 additions (Sprint 19 CTO warnings — free-tier model brittleness, deployment doc as sole operational reference).

- **`README.md`**: status paragraph rewritten. "Status: **V1.1 released** (`v1.1.0`, Sprint 19)..." Structure mirrors current v1.0.0 paragraph. Add a one-line note about the new `openrouter` provider option.

### 4.12 V1.2 lightweight candidate list

In DECISIONS.md #249+ close-out, one paragraph listing V1.2 candidates. No separate document. No phase assignments. No dates.

Candidates (one line each, drawn from Sprints 16–18 explicit deferrals + FOR_CTO.md §16 known limitations):

- Backend/Frontend Engineer split (CLAUDE.md §2.3 target)
- CEO-facing Memory UI (Sprint 18 §8 defer)
- Employee-side memory tool (Sprint 18 out-of-scope)
- Cross-run autonomous learning (Sprint 17/18 out-of-scope)
- Vector/embedding recall (Sprint 18 out-of-scope)
- Second company template (marketing agency / doc studio candidates)
- Second CEO Workspace UX iteration (UX_SPEC §3 PM-conversation + Widget Dock target)
- Employee firing / off-boarding flow (RoleSingletonLock deletion path — FOR_CTO.md §16)
- Merge-conflict CEO resolution UI (currently Mission BLOCKED with no UI — FOR_CTO.md §16)
- Additional providers (AWS Bedrock, Google Vertex, LiteLLM proxy)
- Multi-worker deployment story (currently single asyncio worker — CLAUDE.md §15)
- Broker-backed EventBus (CLAUDE.md §15 future extraction point)

---

## 5. Architecture Requirements

Prefer boundaries equivalent to:

- New file `apps/api/app/modules/provider_gateway/openrouter_provider.py` — implements `ProviderGateway` from scratch (not a subclass of `AnthropicProvider`, per §4.2 rationale).
- `apps/api/app/modules/provider_gateway/gateway.py::build_gateway` gains one branch.
- `apps/api/app/modules/model_registry/registry.py` gains an `openrouter` map.
- `apps/api/app/core/config.py::settings.commander_provider` `Literal` extended; new `openrouter_api_key` setting field.
- `apps/api/app/core/secrets.py::_ENV_DEFAULTS` gains `OPENROUTER_API_KEY` entry.
- `apps/api/app/core/boot_checks.py::validate_boot_config` gains OpenRouter branch.
- New file `apps/api/app/core/logging.py` — the custom `JSONFormatter` (~40 lines) + `install_logging()` helper called from `main.py::lifespan`.
- `apps/api/app/main.py` — adds correlation-ID middleware, calls `install_logging()`.
- `apps/api/app/modules/workflow_engine/engine.py` — sets `task_id` / `agent_id` / `project_id` contextvars at the right boundary points inside `_spawn`, `_run_role`, `_run_engineer_tool_loop`.
- `scripts/verify_real_llm.py` — accepts `--provider` argument.
- `scripts/load_smoke.py` — new script per §4.8.
- `Makefile` — new target for OpenRouter verify.
- `.env.example` — extended.
- New file `.env.production.example`.
- New docs per §4.11.

The new provider is **not** allowed to:
- import from `agent_harness`, `workflow_engine`, `tasks`, `approvals`, or `planning` directly (Rule #1 — same discipline as `AnthropicProvider`).
- read `os.environ` directly for its API key (Rule #7 — goes through `SecretsProvider`).
- log the API key value, echo it in an error message, or return it through any API.
- forward the CEO's `X-Request-Id` header value to OpenRouter (headers sent to OpenRouter are `Authorization`, `Content-Type`, `HTTP-Referer`, `X-Title` only — deterministic, no client-controllable content).

The correlation-ID middleware is **not** allowed to:
- persist the request UUID to any table (Sprint 19 does not add a schema change for correlation).
- trust an incoming `X-Request-Id` header (always generates server-side).
- include the request UUID in Event payloads (contextvar-only in logs; not in the event stream — an event's identity is `event.id`).

The log formatter is **not** allowed to:
- introduce a new logging library dependency.
- change existing logger names (`commander.workflow_engine`, `commander.event_bus`, etc.).
- emit fields whose values contain known secret-shaped content (see §4.9 blocklist).

---

## 6. Provider Integration Requirements

**Wire-format translation** in `OpenRouterProvider`:

Request:
```
Commander complete(model_ref, system, messages=[...], tools=[...])
  → POST https://openrouter.ai/api/v1/chat/completions
       Authorization: Bearer <OPENROUTER_API_KEY>
       HTTP-Referer: https://github.com/anthropics/commander
       X-Title: Commander
       {
         "model": <resolved_model_id>,
         "messages": [{"role": "system", "content": system}, ...messages],
         "tools": [<translated>],
         "max_tokens": <opts.max_tokens or default>
       }
```

Response:
```
OpenAI response → CompletionResult(
  text = choices[0].message.content or "",
  tool_calls = [ToolCallData(call.id, call.function.name, json.loads(call.function.arguments))
                for call in (choices[0].message.tool_calls or [])],
  stop_reason = choices[0].finish_reason,
  input_tokens = usage.prompt_tokens,
  output_tokens = usage.completion_tokens,
  provider = "openrouter",
  model = <resolved_model_id>,
)
```

Tool schema translation:
```
Commander tool: {name, description, input_schema}
OpenAI tool:    {"type": "function", "function": {"name", "description", "parameters"}}
```

`parameters` = Commander's `input_schema` (already a valid JSON Schema from Pydantic).

Stream translation (SSE): OpenAI SSE format (`data: {"choices": [{"delta": {"content": "..."}}]}`) — parse per-chunk `choices[0].delta.content`, yield the string. Usage delta arrives in a final chunk with `choices[0].finish_reason` set and a `usage` object; update the caller's `usage` dict in place, same convention `AnthropicProvider.stream` uses.

**Error mapping:**
- 401/403 → `RuntimeError("OpenRouter rejected the configured API key (HTTP {status}). Check the key in Company Settings.")` — same shape as `AnthropicProvider._legible_error`.
- 429 / 5xx → left as `httpx.HTTPStatusError` for `RoutedProviderGateway._is_retryable` to catch.
- Malformed JSON response → let it raise; the pipeline handler converts to `TASK_FAILED`.

**Tests:**
- Fixture-based tests against a fake httpx transport (mirror `test_anthropic_provider.py` shape).
- One test proving OpenAI tool-schema translation is correct.
- One test proving Anthropic-style `tool_use` blocks are NOT emitted (OpenRouter is OpenAI-style, so the test asserts the OpenAI-style `tool_calls` shape flows through correctly).
- One test proving 401 raises the legible RuntimeError, not the raw httpx error.
- Streaming test proving text chunks arrive in order and `usage` dict is populated on final chunk.

---

## 7. Observability Requirements

### 7.1 Middleware

`apps/api/app/main.py` gains a middleware registered before CORS:

```
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
    finally:
        request_id_var.reset(token)
```

`request_id_var` is a `contextvars.ContextVar[str | None]` defined in `apps/api/app/core/logging.py`.

### 7.2 Workflow contextvars

`CommanderWorkflowEngine._spawn(task_id, ...)` wraps its `_runner()` coroutine in a `task_id_var.set(task_id)` / reset pair. `_run_role` / `_run_engineer_tool_loop` do the same for `agent_id_var` and `project_id_var` around their execution bodies.

Because contextvars propagate through `asyncio.create_task` (Python 3.7+), the log formatter reads them from wherever a log call originates during the workflow, exactly as it does during a request handler.

### 7.3 Formatter

`apps/api/app/core/logging.py`:

```python
import json, logging, uuid
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
task_id_var:    ContextVar[str | None] = ContextVar("task_id", default=None)
agent_id_var:   ContextVar[str | None] = ContextVar("agent_id", default=None)
project_id_var: ContextVar[str | None] = ContextVar("project_id", default=None)

_SECRET_KEYS = frozenset({"password", "token", "key", "secret", "authorization", "cookie"})

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for var, key in [(request_id_var, "request_id"), (task_id_var, "task_id"),
                         (agent_id_var, "agent_id"), (project_id_var, "project_id")]:
            v = var.get()
            if v is not None:
                obj[key] = v
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        # redact secret-shaped keys anywhere in record.__dict__ (defensive)
        for k, v in record.__dict__.items():
            if k.lower() in _SECRET_KEYS:
                obj[k] = "[redacted]"
        return json.dumps(obj, ensure_ascii=False)

def install_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
```

The above is illustrative — final exact code decided at implementation time, but the shape (single formatter, contextvars, redaction, no new dep) is fixed.

### 7.4 Tests

- Log formatter unit test: request contextvars propagate into output JSON.
- Log formatter unit test: secret-shaped field is redacted.
- Middleware integration test: response includes `X-Request-Id` header.
- Middleware integration test: incoming `X-Request-Id` header is IGNORED (server assigns fresh UUID).
- Workflow test: log line emitted from inside `_run_engineer_tool_loop` carries `task_id` and `agent_id`.

---

## 8. Verification Matrix

Sprint 19 verifies the whole V1.1 as-built. Concrete matrix (all rows must PASS by Phase 4 close):

| Verification | Method | Where recorded |
|---|---|---|
| Backend baseline + new tests | `pytest apps/api` | Final report + PROGRESS.txt |
| Dashboard typecheck | `pnpm tsc --noEmit` | Final report |
| Dashboard build | `pnpm next build` | Final report |
| Alembic upgrade round-trip | Real Postgres via `make db-up` + `alembic upgrade head` + `downgrade -1` + `upgrade head` | Final report |
| Fresh-DB bootstrap | `scripts/seed.py` against fresh Postgres | Final report |
| Mock full E2E | Existing test suite (mock provider covers full pipeline already) | Final report |
| Real LLM full E2E — Anthropic direct | `make verify-llm` | Final report + `CHANGELOG.md` |
| Real LLM full E2E — Claude via OpenRouter | `make verify-llm-openrouter` (with model override to `anthropic/claude-sonnet-4.5`) | Final report + `CHANGELOG.md` |
| Real LLM smoke — OpenRouter free tier | `make verify-llm-openrouter` (default free model) | Final report + `docs/KNOWN_ISSUES.md` (quality notes) |
| Load smoke — 4 scenarios | `scripts/load_smoke.py` | Final report + `CHANGELOG.md` operating envelope |
| Fresh-box deployment walkthrough | Follow `docs/DEPLOYMENT.md` on a clean Docker container or VM | Final report + `docs/DEPLOYMENT.md` marked "verified" |
| v1.0 → v1.1 upgrade path | Start from `v1.0.0` tag DB dump (or a synthesized pre-Sprint-9 DB), `git checkout master`, `make db-upgrade`, verify auth flow works | Final report + `docs/DEPLOYMENT.md` upgrade section |
| Whole-system security audit | Dedicated read-only agent, one pass | Final report + DECISIONS.md close-out |
| Correlation ID + log format | Manual inspection of a log line during a real mission run | Final report |

Every row above must produce evidence. "Green" is not a claim; a captured command output or log excerpt is.

---

## 9. Required Behavioral Tests

Add tests following existing patterns:

### OpenRouter provider
- OpenAI-shape request payload verified against a fake httpx transport.
- Tool schema translation (Commander → OpenAI function shape).
- Response translation: `choices[0].message.content` → `text`.
- Tool-call response translation: OpenAI `tool_calls[]` → Commander `ToolCallData` tuple.
- `finish_reason` → `stop_reason` mapping.
- Usage extraction (prompt_tokens → input_tokens, completion_tokens → output_tokens).
- Streaming: chunks arrive in order; `usage` dict populated on final chunk.
- 401/403 → legible RuntimeError; 429/5xx → raw httpx error (for RoutedProviderGateway retry).
- `Authorization: Bearer` header set correctly.
- `HTTP-Referer` and `X-Title` headers set to deterministic values (never client input).
- Malformed OpenRouter response does not crash the provider (raises, does not silently return `text=""`).
- `build_gateway("openrouter", ...)` returns a `RoutedProviderGateway` wrapping `OpenRouterProvider`.
- Model resolution: `resolve("openrouter", "planner-default")` returns the registered OpenRouter model id.
- Boot check: `commander_provider="openrouter"` without `OPENROUTER_API_KEY` fails startup with a legible error.

### Correlation ID / logging
- Log formatter emits JSON with `ts`, `level`, `logger`, `msg`.
- `request_id_var` set → included in output; not set → omitted.
- `task_id_var` set → included; not set → omitted.
- Secret-shaped `record.__dict__` key redacted to `"[redacted]"`.
- Middleware assigns fresh UUID, ignores incoming `X-Request-Id`.
- Middleware includes `X-Request-Id` header in response.
- Contextvar reset after request (does not leak into next request).
- Workflow-engine test: log emitted inside `_run_engineer_tool_loop` carries `task_id`.

### Regression
- Existing tests all pass with the new formatter installed (some may need adjustment if they parse log output — they should not; `caplog` fixture reads records, not formatted strings).
- Existing `AnthropicProvider` tests unchanged.
- Existing `MockProvider` tests unchanged.
- Full backend suite green.
- Role-hardcoding guard remains green.

### Not tested via automation (manually verified per §8 matrix)
- Real LLM full E2E (Anthropic direct + Claude-via-OpenRouter + free-tier smoke).
- Load smoke scenarios.
- Fresh-box deployment walkthrough.
- v1.0 → v1.1 upgrade.

---

## 10. Phases

### Phase 0 — Baseline verification and architecture decisions

1. Verify HEAD, origin/master, working tree clean.
2. Run backend baseline (`pytest apps/api`). Confirm 512 passed / 6 skipped.
3. Run dashboard `tsc --noEmit` and `next build`. Confirm all 19 routes.
4. Verify Alembic head is `c2a7e1f4b6d3` and migration round-trip is clean.
5. Read every file in §3.
6. Inspect current OpenRouter free-tier model list (via https://openrouter.ai/models?free — check what's actually available at Sprint-19-implementation time).
7. Pick default OpenRouter model for each logical ref (`planner-default`, `builder-default`, `reviewer-default`, `advisor-default`). Prefer free tier; fall back to lowest-cost paid if no free-tier tool-use-capable model is available.
8. Decide the final log formatter shape (may deviate slightly from §7.3 illustrative code; record actual choice).
9. Confirm `.env` currently has `OPENROUTER_API_KEY` populated (user has done this).
10. Draft `docs/KNOWN_ISSUES.md` skeleton so Sprint 19's later phases have a place to record findings.
11. Update PROGRESS.txt with Sprint 19 live checklist.
12. Record decisions in DECISIONS.md #249+ (OpenRouter model choice, log formatter shape, load smoke scenarios).
13. Commit/push Phase 0.

### Phase 1 — OpenRouter provider + model registry + boot check

1. Add `openrouter_api_key: str | None = None` to `Settings` in `core/config.py`.
2. Extend `commander_provider: Literal[...]` to include `"openrouter"`.
3. Add `OPENROUTER_API_KEY` to `_ENV_DEFAULTS` in `core/secrets.py`.
4. Extend `boot_checks.validate_boot_config` with the openrouter branch.
5. Extend `model_registry/registry.py` with the `openrouter` map from Phase 0.
6. Implement `apps/api/app/modules/provider_gateway/openrouter_provider.py` per §6.
7. Extend `provider_gateway/gateway.py::build_gateway` with the openrouter branch.
8. Extend `.env.example` with `OPENROUTER_API_KEY=` and a comment referencing the new provider option.
9. Extend `scripts/verify_real_llm.py` with `--provider` argument.
10. Add `make verify-llm-openrouter` target (or equivalent pass-through) to `Makefile`.
11. Add all §9 provider tests.
12. Full backend suite green.
13. Update PROGRESS.txt.
14. Commit/push Phase 1.

### Phase 2 — Correlation ID + structured logging

1. Create `apps/api/app/core/logging.py` with contextvars, `JSONFormatter`, `install_logging()`.
2. Wire `install_logging()` into `main.py::lifespan`.
3. Add correlation-ID middleware to `main.py`.
4. Wrap `CommanderWorkflowEngine._spawn`'s runner in contextvar sets for `task_id` / `project_id`.
5. Set `agent_id_var` around `_run_role` / `_run_engineer_tool_loop` execution bodies.
6. Add all §9 correlation/logging tests.
7. Full backend suite green.
8. Manually inspect a mission run's log output to confirm contextvars propagate (record a sample log line in the final report).
9. Update PROGRESS.txt.
10. Commit/push Phase 2.

### Phase 3 — Verification, load smoke, real-LLM E2E

1. Implement `scripts/load_smoke.py` per §4.8 (all four scenarios).
2. Run load smoke; record evidence (timing, query counts, RSS delta).
3. Fix any genuine bug the smoke reveals; document any scale limit found.
4. Run `make verify-llm` (Anthropic direct); record turn count / tokens / cost / wall time.
5. Run `make verify-llm-openrouter` with model registry pointing to `anthropic/claude-sonnet-4.5` (or Sonnet equivalent OpenRouter routes); record same.
6. Run `make verify-llm-openrouter` with the default free-tier model chosen in Phase 0; record result and any quality issues in `docs/KNOWN_ISSUES.md`.
7. On a clean environment (fresh Docker container, VM, or clean local user), follow `docs/DEPLOYMENT.md` end-to-end. Every ambiguity in the doc gets fixed in the doc during this walk.
8. If v1.0.0 tag exists in git history, check it out, seed a small DB, tag it as "pre-v1.1 state," then `git checkout master`, run `make db-upgrade`, verify auth works. Document the upgrade steps in `docs/DEPLOYMENT.md`.
9. Verify Alembic upgrade-then-downgrade-1-then-upgrade round-trip on real Postgres.
10. Update PROGRESS.txt.
11. Commit/push Phase 3.

### Phase 4 — Security audit, documentation, and release

1. Full backend suite green.
2. Dashboard typecheck + build green.
3. Independent whole-system security audit (dedicated agent, one pass, not per-module):
   - Provider aggregator adds no shell/exec path.
   - `OPENROUTER_API_KEY` never logged, never in an API response, never in a prompt to Anthropic.
   - Correlation-ID middleware ignores incoming header.
   - Log formatter redacts secret-shaped keys.
   - No new public arbitrary-execution endpoint.
   - No new dashboard UI (widget/page/route).
   - No new alembic migration (Sprint 19 adds none).
   - Every accepted tradeoff still holds (§15 items unchanged).
   - Every Sprint 16/17/18 invariant unchanged.
   - Rule #4 (providers replaceable) genuinely holds with 3 providers.
   - Rule #7 (secrets via `SecretsProvider`) holds for OPENROUTER_API_KEY.
   - Rule #11 (CEO's one channel = PM) unchanged.
   - Rule #18 (no silent failure) unchanged.
4. Author `docs/DEPLOYMENT.md` per §4.11 structure.
5. Author `.env.production.example`.
6. Author `docs/KNOWN_ISSUES.md` (consolidated from all sprint deferrals + this sprint's smoke findings).
7. Author `CHANGELOG.md` v1.1.0 entry.
8. Update `README.md` status paragraph.
9. Update `CLAUDE.md` roadmap and status.
10. Update `docs/ARCHITECTURE.md` with new §11 Deployment paragraph.
11. Update `FOR_CTO.md` per §4.11 additions.
12. Add DECISIONS.md #249+ close-out entry (baseline verification result, OpenRouter model choice + reason, correlation ID design rationale, load smoke findings, real-LLM E2E findings, security audit summary, V1.2 candidate list).
13. Verify remote HEAD reflects the final Phase 4 commit; if not, push.
14. Verify every §12 shipping-bar item is true.
15. Create `git tag v1.1.0` (annotated: `git tag -a v1.1.0 -m "V1.1 released — see CHANGELOG.md"`).
16. Push the tag: `git push origin v1.1.0`.
17. Verify `git ls-remote --tags origin` shows `v1.1.0` at the expected commit.
18. Final commit closing PROGRESS.txt.
19. Verify local HEAD == origin/master, working tree clean.

---

## 11. Definition of Shipping (V1.1 tag criteria)

`v1.1.0` MUST NOT be tagged unless every item below is verifiably true. If any item is unverified or false, the sprint may be marked complete but the tag does not exist. Do not fake verification.

1. Local HEAD == origin/master, working tree clean.
2. Full backend suite green (baseline 512 + Sprint 19 new tests, zero regressions outside Sprint 19 files).
3. Dashboard typecheck (`pnpm tsc --noEmit`) green; dashboard build (`pnpm next build`) green.
4. Alembic head is `c2a7e1f4b6d3` (Sprint 19 adds no migration); upgrade-downgrade-upgrade round-trip on real Postgres passes.
5. Fresh-DB bootstrap via `scripts/seed.py` completes end-to-end.
6. `COMMANDER_PROVIDER` accepts `mock` | `anthropic` | `openrouter`.
7. `OpenRouterProvider` exists, reads its key only through `SecretsProvider`, is exercised by unit tests + one real-LLM run.
8. Real-LLM full E2E — Anthropic direct — completed successfully with recorded evidence (turn count, tokens, cost, wall time).
9. Real-LLM full E2E — Claude via OpenRouter — completed successfully with recorded evidence.
10. Real-LLM smoke — free-tier OpenRouter model — attempted; result (pass or documented failure mode) recorded in `docs/KNOWN_ISSUES.md`.
11. Load smoke — all four §4.8 scenarios ran; results recorded in the final report AND `CHANGELOG.md` operating envelope note.
12. Correlation ID middleware installed; `X-Request-Id` header set in every response; server-issued UUID; ignores incoming header.
13. Structured JSON log formatter installed; contextvars (`request_id`, `task_id`, `agent_id`, `project_id`) appear in log lines when set; secret-shaped keys redacted.
14. No new dashboard UI, no new widget, no new page, no new API endpoint (§4.10).
15. `docs/DEPLOYMENT.md` exists; a Phase 3 fresh-box walkthrough followed it successfully; the doc contains prerequisites, first-deploy walkthrough, production run recipe, `.env.production.example` reference, optional HTTPS section, backup/restore instructions, and v1.0 → v1.1 upgrade path.
16. `.env.production.example` committed.
17. `docs/KNOWN_ISSUES.md` exists and consolidates: accepted tradeoffs (CLAUDE.md §15), Sprint 15–18 explicit deferrals, Sprint 19 verified operating envelope, provider variance notes, upgrade caveats.
18. `CHANGELOG.md` v1.1.0 entry summarizes every Sprint 9–19 landing and calls out breaking changes.
19. `CLAUDE.md` roadmap marks `19 ✅` and status line reflects `V1.1 released`.
20. `docs/ARCHITECTURE.md` has a new §11 Deployment paragraph; §9 accepted tradeoffs unchanged.
21. `docs/DECISIONS.md` #249+ close-out entry recorded.
22. `FOR_CTO.md` updated per §4.11.
23. `README.md` status paragraph updated to `V1.1 released (v1.1.0, Sprint 19)`.
24. Independent whole-system security audit passed with zero CONCERN/FAIL items.
25. Every Sprint 16/17/18 invariant unchanged (spot-verified in audit).
26. Every CLAUDE.md §15 accepted tradeoff still valid (no accidental "fix" leaked into Sprint 19).
27. `git tag -a v1.1.0` created against the final Phase 4 commit.
28. `git push origin v1.1.0` executed; `git ls-remote --tags origin` confirms.

If items 15 or 24 fail, do not tag. If items 8 or 9 fail, do not tag. If item 11 reveals a genuine bug that cannot be fixed inside Sprint 19, do not tag — file a Sprint 20 blocker instead.

---

## 12. Out of Scope

Do not implement:

- New CEO-facing UI (widget, page, MissionDetail extension, SpecificationDetail extension, Timeline extension).
- New API endpoints (backend or admin).
- Production Docker Compose file (`docker-compose.prod.yml` or similar).
- Backup automation script (documentation of `pg_dump`/`tar` is enough).
- Rate limiting middleware / throttling.
- Metrics collection infrastructure (Prometheus exporter, StatsD, OpenTelemetry export).
- Log aggregation infrastructure (ELK, Loki, Fluent Bit config).
- HTTPS terminator configuration (nginx config beyond a small optional example in `docs/DEPLOYMENT.md`).
- Load testing framework (k6, JMeter, Locust, wrk).
- Any new schema migration (Sprint 19 adds no migration).
- Any change to existing accepted tradeoffs (CLAUDE.md §15).
- Any V1.2 candidate feature (Memory UI, Employee memory tool, RAG, vector recall, second template, Backend/Frontend Engineer split, additional providers, firing flow, merge-conflict UI, multi-worker, broker EventBus).
- Any new logging dependency (`python-json-logger`, `structlog`).
- Persisting the correlation ID to any table.
- Changing any existing logger name.
- Reading an incoming `X-Request-Id` header (always server-issued).
- Any per-user or per-Company rate limit on OpenRouter calls (deferred to provider config).
- Automated cost/budget guard for OpenRouter (existing mission budget guard already applies).
- Anything from Sprint 18's out-of-scope list (RAG, vector, cross-Company, Employee memory tool, autonomous cross-Mission learning, additional Memory categories).

If a V1.2 need appears mid-implementation, record it as a follow-up in the DECISIONS.md close-out entry — do not implement.

---

## 13. Final Report

Return one evidence-based report containing:

1. Starting / final / origin SHA and working-tree state.
2. Sprint result and DoD checklist count (28 items).
3. Commits and their rationale.
4. Any repository divergences discovered.
5. OpenRouter provider design and free-tier model choice (from Phase 0).
6. Correlation ID + log format design.
7. Verification matrix (§8 rows, each with evidence).
8. Real-LLM E2E evidence: Anthropic direct (turns/tokens/cost/wall time), Claude via OpenRouter (same), OpenRouter free-tier smoke (result + quality notes).
9. Load smoke evidence: four scenarios with numbers.
10. Fresh-box deployment walkthrough result: what worked, what needed doc fixes.
11. v1.0 → v1.1 upgrade path evidence.
12. Independent security audit result with file/line evidence.
13. Test count delta: baseline 512 → final N; classification of any modified existing tests.
14. Existing-feature compatibility: planning, specifications, missions, workspace, widgets, harness, self-correction, memory.
15. Documentation deliverables checklist (DEPLOYMENT.md, .env.production.example, KNOWN_ISSUES.md, CHANGELOG.md, README, CLAUDE.md, ARCHITECTURE.md, DECISIONS.md, FOR_CTO.md).
16. Residual risks and low-confidence areas (free-tier provider variance, deployment doc first-use fragility, load smoke coverage boundaries).
17. Scope control: confirm nothing V1.2-candidate leaked into the diff.
18. V1.2 lightweight candidate list.
19. `v1.1.0` tag confirmation: `git tag -l v1.1.0` result + `git ls-remote --tags origin` confirming push.
20. Final state (clean tree, HEAD == origin/master).

Begin with Phase 0 and continue through Phase 4 without routine confirmation.
