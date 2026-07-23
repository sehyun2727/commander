"""Projects module.

Owns project entities: create, list, archive. Publishes project.* events.
Other modules never import this module directly — they reference a project
only by project_id, so project ownership doesn't leak across boundaries.

No implementation yet (Sprint 1 defines module boundaries only).
"""
