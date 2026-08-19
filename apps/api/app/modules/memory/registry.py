"""Sprint 18 §4.1/§4.5/§4.9/§4.10 -- frozen, code-owned Project Memory
category list, tag-derivation vocabulary, tokenizer, and deterministic
recall/ranking constants. Mirrors `workspace_widgets/registry.py`'s
"frozen tuple + code-owned constants" pattern: there is no admin route or
CEO action that can add a seventh category (Rule #14 -- Memory has no
mutation surface of its own).
"""

from __future__ import annotations

from ...core.events.types import EventType

CEO_APPROVALS = "ceo_approvals"
PM_SPECIFICATIONS = "pm_specifications"
REVIEWER_FEEDBACK = "reviewer_feedback"
FAILED_ATTEMPTS = "failed_attempts"
SUCCESSFUL_SOLUTIONS = "successful_solutions"
PRIOR_DISCUSSIONS = "prior_discussions"

# sprint-18.md §4.1: the six categories Sprint 18 populates. `architecture_
# decisions` and `coding_conventions` (docs/ARCHITECTURE.md §5's other two)
# are explicitly deferred -- no event in the current stream carries them as
# first-class structured facts (DECISIONS.md #243).
CATEGORIES: tuple[str, ...] = (
    CEO_APPROVALS,
    PM_SPECIFICATIONS,
    REVIEWER_FEEDBACK,
    FAILED_ATTEMPTS,
    SUCCESSFUL_SOLUTIONS,
    PRIOR_DISCUSSIONS,
)

# One projected EventType -> category. The single source of truth for which
# EventTypes the subscriber/backfill project, and which extractor to call.
PROJECTED_EVENT_TYPES: dict[EventType, str] = {
    EventType.APPROVAL_GRANTED: CEO_APPROVALS,
    EventType.APPROVAL_REJECTED: CEO_APPROVALS,
    EventType.APPROVAL_CHANGES_REQUESTED: CEO_APPROVALS,
    EventType.SPECIFICATION_APPROVED: PM_SPECIFICATIONS,
    EventType.REVIEW_COMPLETED: REVIEWER_FEEDBACK,
    EventType.TASK_FAILED: FAILED_ATTEMPTS,
    EventType.TASK_COMPLETED: SUCCESSFUL_SOLUTIONS,
    EventType.SPECIFICATION_TURN_POSTED: PRIOR_DISCUSSIONS,
}

# --- Bounded content (sprint-18.md §4.4) -------------------------------------

MAX_TITLE_LENGTH = 200
MAX_FIELD_BYTES = 2048  # per excerpted text field inside content_json
MAX_CONTENT_JSON_BYTES = 8192  # 8 KiB total serialized content_json
MAX_TAG_COUNT = 16
MAX_TAG_LENGTH = 64
MAX_KEYWORD_COUNT = 16
MAX_KEYWORD_LENGTH = 64
MAX_KEYWORDS_TEXT_LENGTH = 4096

# --- Recall bounds -- server-enforced regardless of what the PM asks for
# (sprint-18.md §4.10) ---------------------------------------------------------

MAX_RECALL_LIMIT = 10
MAX_RECALL_LOOKBACK_DAYS = 365

# --- Ranking (sprint-18.md §4.9, DECISIONS.md #243) --------------------------
# `1 / (1 + age_days / HALF_LIFE_DAYS)` was chosen over `exp(-age_days /
# HALF_LIFE_DAYS)` for exactness/reproducibility across Python versions
# (age_days == HALF_LIFE_DAYS always scores exactly 0.5). Never zero, never
# negative, monotonic in age -- do not switch formulas mid-implementation.
HALF_LIFE_DAYS = 30.0


def recency_decay(age_days: float) -> float:
    return 1.0 / (1.0 + max(age_days, 0.0) / HALF_LIFE_DAYS)


# --- Tokenizer (sprint-18.md §4.5) --------------------------------------------
# Pure Python only: lowercase, whitespace-split, strip to alphanumeric, drop
# a small fixed stopword list and empties, dedupe preserving first-seen
# order. No NLP dependency, no stemming (DECISIONS.md #243).

STOPWORDS = frozenset({"the", "a", "and", "of", "to", "for", "in", "on", "is", "it"})


def tokenize(text: str) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for raw in text.lower().split():
        token = "".join(ch for ch in raw if ch.isalnum())
        if not token or token in STOPWORDS or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens
