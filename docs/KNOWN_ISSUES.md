# Known Issues — Commander

One consolidated list of accepted tradeoffs, deferred scope, and verified
operational limits, as of Sprint 19 (`v1.1.0`). This document exists so an
operator or CTO reading the repository does not have to reconstruct "is this
a bug or a known limit" from `git log` and `docs/DECISIONS.md` alone.

> Status: Phase 0 skeleton. Sections below are filled in as Sprint 19
> Phases 3-4 produce their evidence (load smoke results, real-LLM E2E
> findings, deployment walkthrough notes). Do not treat an empty section as
> "no issues" until Phase 4 closes this document out.

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

_TODO — filled in during Phase 3 from `scripts/load_smoke.py` evidence._

| Scenario | Assertion | Result |
| --- | --- | --- |
| 1 Company × 10 sequential Missions | 10th mission ≤ 1.5× 1st wall time; RSS growth < 100 MB | TBD |
| 3 Companies × 3 concurrent Missions | all reach `pending_approval`, no deadlock, SSE stays connected | TBD |
| Hot-path query counts | constant query count vs. scale; harness dispatch bounded writes | TBD |
| Memory recall @ 1,000 records | < 200 ms wall-clock, fresh connection | TBD |

## 7. Provider variance — free-tier models (§4.5)

_TODO — filled in during Phase 3 from the OpenRouter free-tier full-E2E
smoke test against `openai/gpt-oss-20b:free` (see `docs/DECISIONS.md`
#249 for why this model was chosen)._

Success of this smoke test proves OpenRouter provider wiring works. It does
**not** certify any specific free model as production-quality — free-tier
models are known to vary in tool-call reliability and JSON-formatting
discipline turn to turn.

## 8. v1.0 → v1.1 upgrade caveats

_TODO — filled in during Phase 4 alongside `docs/DEPLOYMENT.md` §7. Notably:
v1.0.0 predates the Sprint 9 auth schema (`users`/`sessions` tables) —
upgrading requires running the `fa793dce62cb_accounts_and_sessions`
migration and manually attributing any pre-auth Company data to a CEO
account (no `owner_id` existed before)._
