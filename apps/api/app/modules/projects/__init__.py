"""Projects module.

Owns project entities: create, list, archive. Publishes project.* events
and (on create) triggers agent_runtime.create_department to hire the
default PM/Engineer/Reviewer Department. Other modules never import this
module directly — they reference a project only by project_id.
"""

from .routes import router

__all__ = ["router"]
