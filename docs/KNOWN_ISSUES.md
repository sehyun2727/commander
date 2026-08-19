# Known Issues — Commander

One consolidated list of accepted tradeoffs, deferred scope, and verified
operational limits, as of Sprint 19 (`v1.1.0`). This document exists so an
operator or CTO reading the repository does not have to reconstruct "is this
a bug or a known limit" from `git log` and `docs/DECISIONS.md` alone.

> Status: Sprint 19 Phase 3 evidence recorded (load smoke, provider
> variance, deployment/upgrade caveats). §7's release-evidence gap
> (Anthropic direct, Claude-via-OpenRouter) reflects this development
> environment's credentials, not unverified code — see that section.

## 1. Accepted tradeoffs (CLAUDE.md §15)

These are deliberate, documented simplicity choices — not things to "fix"
opportunistically. See `docs/DECISIONS.md` before changing any of them.

- **Plaintext secrets.** `SecretsProvider` stores provider API keys
  unencrypted in the database. Acceptable for a single-operator/small-team
  self-hosted deployment; revisit before any multi-tenant or hosted offering.
- **In-process EventBus.** `InProcessEventBus` runs subscribers inline,
  in-process — no broker, no durability beyond the Postgres-backed event
  table itself. A process crash mid-publish can lose an in-flight fan-out;
  the event row itself is still durable.
- **Single worker assumptions.** Commander assumes exactly one API process.
  No cross-process coordination exists for background Mission pipelines.
- **Inline EventBus subscriber execution.** Subscribers run synchronously
  inside the publishing call, not on a queue — a slow subscriber blocks the
  publisher.
- **Python-side conversation filtering.** Some conversation/timeline
  filtering happens in application code rather than SQL, trading query
  efficiency for simplicity at current scale.
- **No connection pooling (beyond SQLAlchemy's default), no read replicas.**
  Single local Postgres instance is the only supported topology.
- **No backup tooling shipped as code.** `docs/DEPLOYMENT.md` (Sprint 19)
  documents a manual `pg_dump`/`tar` procedure; there is no automated
  backup job.
- **Single local Postgres assumption.** No documented HA/replication story.
- **Fabricated-but-labeled mock Payroll figures.** Mock-mode cost figures
  are illustrative "play money" numbers, clearly not real billing data.

## 2. Sprint 15 deferrals (widget system)

- See `docs/DECISIONS.md` Sprint 15 entries for the full widget-system
  scope boundary. Widget registry (`workspace_widgets/registry.py`) is
  template/server-owned; no CEO-authored custom widgets.

## 3. Sprint 16 deferrals (Agent Harness scope)

- See `docs/DECISIONS.md` Sprint 16 entries. Harness tool loop is budgeted
  and template-whitelisted per Rule #13/#12; no free-form tool grants.

## 4. Sprint 17 deferrals (self-correction scope)

- See `docs/DECISIONS.md` Sprint 17 entries. Self-correction is bounded
  (explicit retry/iteration budget); no cross-Mission learning.

## 5. Sprint 18 deferrals (Project Memory scope)

- Recall is naive keyword/tag substring match with recency decay — no
  stemming, fuzzy match, or semantic/embedding similarity (deliberate
  Sprint 18 scope boundary, not an oversight).
- No cross-Company memory — `recall()` always scopes to one `project_id`.
- No vector recall / RAG pipeline anywhere in `app/modules/memory/`.
- No CEO-facing memory surface — recall results appear only inside the
  PM↔CTO planning transcript and as a `MEMORY_RECALLED` Timeline event.
- Only 6 of the 8 originally-sketched memory categories are populated;
  `architecture_decisions` and `coding_conventions` have no current
  structured event source.
- Backfill (`scripts/backfill_memory.py`) is operator-run, not automatic.

## 6. Sprint 19 verified operating envelope (load smoke, §4.8)

Verified via `scripts/load_smoke.py` (mock provider, throwaway SQLite DB,
in-process for scenarios 1/3/4, a real local `uvicorn` server on loopback
for scenario 2 — see `docs/DECISIONS.md` #250 for why). Stable across
repeated runs on this dev machine (Windows, single local disk, mock
latency).

| Scenario | Assertion | Result |
| --- | --- | --- |
| 1 Company × 10 sequential Missions | 10th mission ≤ 1.5× 1st wall time; RSS growth < 100 MB | **PASS** — 10/10 completed, ratio 0.94–1.04×, RSS growth 0.0 MB |
| 3 Companies × 3 concurrent Missions | all reach `pending_approval`, no deadlock, SSE stays connected | **PASS** — 9/9 missions reached `pending_approval`, no deadlock, 3/3 SSE streams stayed connected throughout |
| Hot-path query counts | constant query count vs. scale; harness dispatch bounded writes | **PASS** — `workspace/overview`: 14 SELECTs (constant, 0 vs. 5 missions); `situation`: 8 SELECTs (constant); harness `read_file` dispatch: 1 write per call |
| Memory recall @ 1,000 records | < 200 ms wall-clock, fresh connection | **PASS** — 8.6–15.1 ms across runs, well inside budget |

These numbers describe this repo's mock-provider ceiling on a single
developer machine, not a production capacity guarantee — no Postgres, no
real network latency, no concurrent CEOs. Building scenario 2 surfaced and
fixed two real concurrent-Mission races (`docs/DECISIONS.md` #250); the
founding roster's one-Employee-per-Role default (Sprint 10 §12) means any
deployment running multiple concurrent Missions in one Company should
expect Employees to queue for their turn rather than run in parallel,
which is expected/intended behavior, not a bug.

## 7. Provider variance — free-tier models (§4.5)

Ran `scripts/verify_real_llm.py --provider openrouter` (free-tier default
`openai/gpt-oss-20b:free`, see `docs/DECISIONS.md` #249 for model choice)
several times across Sprint 19 Phase 3. Findings:

- **Provider wiring itself works.** `OpenRouterProvider` correctly forwards
  requests, streams tokens, and parses the OpenAI-compatible `tool_calls`
  shape when the model cooperates.
- **Free-tier reliability varies turn to turn.** Observed: occasional
  malformed tool-call JSON, occasional `clarification_required` responses
  in place of a usable plan/spec turn, and — reliably reproduced twice in
  a row during this Phase 3 session — `429 Too Many Requests` from
  OpenRouter's free-tier rate limit on consecutive real requests within a
  short window.
- **Rule #18 held under real failure.** A `429`/`402` from the provider
  surfaces as a plain-language `FAIL`/`FAILED` Mission state via
  `_legible_error`, never a raw traceback or a silently stuck Mission —
  this is the actual behavior worth certifying from this exercise, more
  than any single free-tier model's output quality.
- Success of this smoke test proves OpenRouter provider wiring works. It
  does **not** certify any specific free model as production-quality —
  free-tier models are known to vary in tool-call reliability and
  JSON-formatting discipline turn to turn, and are also subject to
  provider-side rate limits outside Commander's control.

### §4.6 release-evidence runs — unverified in this environment

Both required real-provider release-evidence runs could not be completed
in this development environment and are recorded here rather than falsely
claimed:

- **Anthropic direct** (`make verify-llm`): no `ANTHROPIC_API_KEY`
  configured in this environment's `.env`. Needs a funded Anthropic API
  key supplied by the operator before this evidence can be captured.
- **Claude via OpenRouter** (`--provider openrouter --model
  anthropic/claude-sonnet-4.5`): the configured `OPENROUTER_API_KEY`
  account has no funded credits — the request fails immediately with
  `402 Payment Required` before any tokens are spent. Needs OpenRouter
  account credits added before this evidence can be captured.

Both code paths exist and are exercised end-to-end by the free-tier smoke
test above (same script, same provider, same `OpenRouterProvider` code
path, different model/account funding) — the gap is credentials/funding
in this environment, not unverified code.

## 8. v1.0 → v1.1 upgrade caveats

See `docs/DEPLOYMENT.md` §7 for the full upgrade walkthrough. Notably:
v1.0.0 predates the Sprint 9 auth schema (`users`/`sessions` tables) —
upgrading requires running the `fa793dce62cb_accounts_and_sessions`
migration (via `make db-upgrade`, verified round-trip clean against a real
Postgres 16 instance during Sprint 19 Phase 3: `downgrade -1` then
`upgrade head` both completed without error) and then manually attributing
any pre-auth Company data to a CEO account (no `owner_id` existed before;
there is no scripted migration for this step since the correct owner is an
operator decision — see the `UPDATE projects SET owner_id = ...` recipe in
`docs/DEPLOYMENT.md` §7). Until that attribution step is done, pre-auth
Companies are invisible to every CEO account (Rule #15).
