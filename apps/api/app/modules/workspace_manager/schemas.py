from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class FileEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    path: str


class MergeRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    commit_sha: str
    subject: str
    merged_at: str


class FileContentResponse(BaseModel):
    path: str
    content: str
