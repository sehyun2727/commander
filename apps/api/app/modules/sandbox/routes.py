from __future__ import annotations

from fastapi import APIRouter, Depends

from ...deps import get_sandbox_runner
from .schemas import CapabilityResponse

router = APIRouter(tags=["sandbox"])


@router.get("/api/system/capabilities", response_model=CapabilityResponse)
async def get_capabilities(sandbox_runner=Depends(get_sandbox_runner)):
    capability = await sandbox_runner.capability()
    return CapabilityResponse(execution=capability.available, reason=capability.reason)
