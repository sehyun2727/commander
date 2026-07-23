"""Auth module.

Owns authentication for the CEO Dashboard (session/token issuance for the
single local user). Used only by the API layer's request handling — no
other domain module depends on it, and it depends on none of them.

No implementation yet (Sprint 1 defines module boundaries only).
"""
