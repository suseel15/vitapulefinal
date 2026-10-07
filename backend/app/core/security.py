from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings, get_settings

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_profile(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    if not settings.supabase_is_configured:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication is not configured.")

    headers = {
        "apikey": settings.supabase_publishable_key,
        "Authorization": f"Bearer {credentials.credentials}",
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            auth_response = await client.get(f"{settings.supabase_url}/auth/v1/user", headers=headers)
            if auth_response.status_code == status.HTTP_401_UNAUTHORIZED:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is not valid.")
            auth_response.raise_for_status()
            user = auth_response.json()
            user_id = UUID(user["id"])

            profile_response = await client.get(
                f"{settings.supabase_url}/rest/v1/profiles",
                headers=headers,
                params={"id": f"eq.{user_id}", "select": "id,role,display_name", "limit": "1"},
            )
            profile_response.raise_for_status()
            profiles = profile_response.json()
    except HTTPException:
        raise
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The identity provider is temporarily unavailable.",
        ) from error

    if not profiles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="An approved account profile is required.")
    profile = profiles[0]
    profile["email"] = user.get("email")
    role = profile.get("role")
    if role not in {"ATHLETE", "DOCTOR", "ADMIN"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account role is not authorized.")
    if role == "ATHLETE":
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                application_response = await client.get(
                    f"{settings.supabase_url}/rest/v1/doctor_applications",
                    headers=headers,
                    params={"profile_id": f"eq.{user_id}", "select": "status", "limit": "1"},
                )
                application_response.raise_for_status()
                applications = application_response.json()
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The identity provider is temporarily unavailable.",
            ) from error
        if applications:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Doctor access applications must be resolved before this account can be used.",
            )
    return profile


def require_roles(*allowed_roles: str) -> Callable[..., Any]:
    normalized_roles = frozenset(role.upper() for role in allowed_roles)

    async def role_dependency(
        profile: Annotated[dict[str, Any], Depends(get_current_profile)],
    ) -> dict[str, Any]:
        if profile["role"] not in normalized_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This action is not allowed for your account.")
        return profile

    return role_dependency
