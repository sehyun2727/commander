from __future__ import annotations

from pydantic import BaseModel


class AgentCostEntry(BaseModel):
    agent_id: str
    total_usd: float


class ProjectCostSummary(BaseModel):
    project_id: str
    month_total_usd: float
    by_agent: list[AgentCostEntry]


class TaskCostSummary(BaseModel):
    task_id: str
    total_usd: float
