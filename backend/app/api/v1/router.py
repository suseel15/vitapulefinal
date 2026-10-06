from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.core.responses import success
from app.core.security import get_current_profile
from app.api.v1.devices import router as devices_router
from app.api.v1.health import router as health_router
from app.api.v1.ml import router as ml_router
from app.api.v1.rehab import router as rehab_router
from app.api.v1.wellbeing import router as wellbeing_router

router = APIRouter()
router.include_router(health_router)
router.include_router(rehab_router)
router.include_router(ml_router)
router.include_router(devices_router)
router.include_router(wellbeing_router)


@router.get("/health")
async def versioned_health(request: Request) -> dict:
    return success(request, {"status": "ok"})


@router.get("/ready")
async def versioned_ready(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if not settings.supabase_is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Required identity-provider configuration is missing.",
        )
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(
                f"{settings.supabase_url}/auth/v1/settings",
                headers={"apikey": settings.supabase_publishable_key},
            )
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A required service is not responding.",
        ) from error
    return success(request, {"status": "ready"})


@router.get("/me")
async def current_account(
    request: Request,
    profile: Annotated[dict, Depends(get_current_profile)],
) -> dict:
    return success(request, {"profile": profile})
