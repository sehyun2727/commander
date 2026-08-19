"""Project Memory module (Sprint 18) -- "Company Knowledge".

Deterministic, event-derived projection of six categories of company
history into `memory_records` (Rule #14: memory is a projection over the
event stream, never a second source of truth). No dedicated
`MemoryService` singleton in `lifespan` (mirrors `tasks/service.py` /
`planning/service.py`), just plain async functions plus the one-time
subscriber wiring call below.
"""

from .backfill import backfill_memory
from .registry import CATEGORIES
from .schemas import MemoryRecord, RecallRequest, RecalledMemory
from .service import record_memory, recall
from .subscriber import install_memory_subscribers

__all__ = [
    "CATEGORIES",
    "MemoryRecord",
    "RecallRequest",
    "RecalledMemory",
    "backfill_memory",
    "record_memory",
    "recall",
    "install_memory_subscribers",
]
