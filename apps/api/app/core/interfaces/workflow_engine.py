"""Port: the Workflow Engine — Commander's orchestration brain.

Concrete implementation lives in modules/workflow_engine. The API layer
depends only on this interface — per docs/ARCHITECTURE.md, "no AI logic
exists" in the API Server itself.

Method-to-responsibility mapping (see docs/backend/workflow/PM_RESPONSIBILITY.md):
  - handle_ceo_request  -> receive CEO requests, understand them (PM)
  - create_work_item    -> create work items (PM)
  - assign_agent        -> assign agents (PM)
  - monitor_progress    -> monitor progress (PM + Reports)
  - handle_failure      -> detect failures (see FAILURE_HANDLING.md)

"Publish events" is deliberately not a separate method here: every
implementation depends on EventBus (see docs/backend/DEPENDENCIES.md) and
publishes through it directly. Adding a proxy method would just forward to
EventBus.publish with no added contract value.
"""

from abc import ABC, abstractmethod

from ..lifecycle.task_states import TaskState


class WorkflowEngine(ABC):
    @abstractmethod
    def handle_ceo_request(self, project_id: str, instruction: str) -> str:
        """Receive a CEO natural-language request for a project; return a
        request_id. Triggers PM interpretation and task breakdown."""

    @abstractmethod
    def create_work_item(self, project_id: str, title: str, priority: str = "normal") -> str:
        """Create a task derived from CEO intent or PM planning. Returns
        task_id. Caller (PM) decides priority."""

    @abstractmethod
    def assign_agent(self, task_id: str, agent_role: str) -> None:
        """Assign a task to an agent role via Agent Runtime."""

    @abstractmethod
    def monitor_progress(self, task_id: str) -> TaskState:
        """Return a task's current lifecycle state."""

    @abstractmethod
    def handle_failure(self, task_id: str, error: Exception) -> None:
        """React to a failure raised during task execution: decide retry,
        escalate to CEO approval, or mark failed. See FAILURE_HANDLING.md."""
