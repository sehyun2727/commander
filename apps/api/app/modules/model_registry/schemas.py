from __future__ import annotations

from pydantic import BaseModel


class ModelCatalogEntry(BaseModel):
    role: str
    current_model: str
    recommended_model: str
    options: list[str]


class SetModelRequest(BaseModel):
    model: str
