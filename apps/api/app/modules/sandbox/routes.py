from __future__ import annotations

from fastapi import APIRouter, Depends

from ...deps import get_sandbox_runner, get_session_factory
from .schemas import CapabilityResponse, ExecutionSettingsResponse, SetExecutionEnabledRequest
from .settings import get_execution_enabled, set_execution_enabled

router = APIRouter(tags=["sandbox"])


@router.get("/api/system/capabilities", response_model=CapabilityResponse)
async def get_capabilities(sandbox_runner=Depends(get_sandbox_runner)):
    capability = await sandbox_runner.capability()
    return CapabilityResponse(execution=capability.available, reason=capability.reason)


@router.get(
    "/api/projects/{project_id}/execution-settings", response_model=ExecutionSettingsResponse
)
async def get_execution_settings(
    project_id: str,
    sandbox_runner=Depends(get_sandbox_runner),
    session_factory=Depends(get_session_factory),
):
    capability = await sandbox_runner.capability()
    enabled = await get_execution_enabled(session_factory, project_id)
    return ExecutionSettingsResponse(
        execution_available=capability.available, reason=capability.reason, execution_enabled=enabled
    )


@router.put(
    "/api/projects/{project_id}/execution-settings", response_model=ExecutionSettingsResponse
)
async def put_execution_settings(
    project_id: str,
    body: SetExecutionEnabledRequest,
    sandbox_runner=Depends(get_sandbox_runner),
    session_factory=Depends(get_session_factory),
):
    await set_execution_enabled(session_factory, project_id, body.enabled)
    capability = await sandbox_runner.capability()
    return ExecutionSettingsResponse(
        execution_available=capability.available, reason=capability.reason, execution_enabled=body.enabled
    )
