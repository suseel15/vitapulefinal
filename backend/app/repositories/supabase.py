from typing import Any
from urllib.parse import quote, urljoin

import httpx
from fastapi import HTTPException, status

from app.core.config import Settings


class SupabaseRepository:
    def __init__(self, settings: Settings, access_token: str, *, service_role: bool = False) -> None:
        if not settings.supabase_is_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Health data is not configured.",
            )
        if service_role and not settings.supabase_service_role_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Secure health data processing is not configured.",
            )
        self.settings = settings
        self._service_role = service_role
        self._token = settings.supabase_service_role_key if service_role else access_token

    @property
    def headers(self) -> dict[str, str]:
        api_key = self.settings.supabase_service_role_key if self._service_role else self.settings.supabase_publishable_key
        return {
            "apikey": api_key,
            "Authorization": f"Bearer {self._token}",
        }

    async def rest(
        self,
        method: str,
        table: str,
        *,
        params: dict[str, str] | None = None,
        payload: Any = None,
        prefer: str | None = None,
    ) -> Any:
        headers = {**self.headers, "Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if prefer:
            headers["Prefer"] = prefer
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.request(
                    method,
                    f"{self.settings.supabase_url}/rest/v1/{quote(table, safe='')}",
                    params=params,
                    headers=headers,
                    json=payload,
                )
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The health data service is temporarily unavailable.",
            ) from error
        if not response.is_success:
            mapped_status = (
                status.HTTP_404_NOT_FOUND
                if response.status_code == 404
                else status.HTTP_409_CONFLICT
                if response.status_code == 409
                else status.HTTP_400_BAD_REQUEST
                if response.status_code in {400, 422}
                else status.HTTP_503_SERVICE_UNAVAILABLE
            )
            raise HTTPException(
                status_code=mapped_status,
                detail="The health data request could not be completed.",
            )
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The health data service returned an invalid response.",
            ) from error

    async def rpc(self, function_name: str, payload: dict[str, Any]) -> Any:
        if not function_name.replace("_", "").isalnum():
            raise ValueError("RPC function name is invalid.")
        headers = {**self.headers, "Accept": "application/json", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self.settings.supabase_url}/rest/v1/rpc/{quote(function_name, safe='')}",
                    headers=headers,
                    json=payload,
                )
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The health data service is temporarily unavailable.",
            ) from error
        if not response.is_success:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The requested account action could not be completed.",
            )
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The health data service returned an invalid response.",
            ) from error

    async def upload_object(
        self,
        bucket: str,
        object_path: str,
        content: bytes,
        mime_type: str,
        *,
        upsert: bool = False,
    ) -> None:
        headers = {**self.headers, "Content-Type": mime_type, "x-upsert": str(upsert).lower()}
        url = (
            f"{self.settings.supabase_url}/storage/v1/object/"
            f"{quote(bucket, safe='')}/{quote(object_path, safe='/')}"
        )
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(url, headers=headers, content=content)
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Private report storage is temporarily unavailable.",
            ) from error
        if not response.is_success:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The report could not be saved to private storage.",
            )

    async def download_object(self, bucket: str, object_path: str) -> bytes:
        url = (
            f"{self.settings.supabase_url}/storage/v1/object/"
            f"{quote(bucket, safe='')}/{quote(object_path, safe='/')}"
        )
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.get(url, headers=self.headers)
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Private report storage is temporarily unavailable.",
            ) from error
        if response.status_code == 404:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The requested source report is unavailable.")
        if not response.is_success:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Private report storage is temporarily unavailable.",
            )
        return response.content

    async def delete_object(self, bucket: str, object_path: str) -> None:
        url = (
            f"{self.settings.supabase_url}/storage/v1/object/"
            f"{quote(bucket, safe='')}/{quote(object_path, safe='/')}"
        )
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.delete(url, headers=self.headers)
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Private report storage cleanup could not be completed.",
            ) from error
        if not response.is_success and response.status_code != 404:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Private report storage cleanup could not be completed.",
            )

    async def signed_url(self, bucket: str, object_path: str, expires_in: int) -> str:
        url = (
            f"{self.settings.supabase_url}/storage/v1/object/sign/"
            f"{quote(bucket, safe='')}/{quote(object_path, safe='/')}"
        )
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.post(
                    url,
                    headers={**self.headers, "Content-Type": "application/json"},
                    json={"expiresIn": expires_in},
                )
        except httpx.HTTPError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="A secure source link could not be created.",
            ) from error
        if not response.is_success:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="A secure source link could not be created.",
            )
        try:
            signed_path = response.json()["signedURL"]
        except (ValueError, KeyError) as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The storage service returned an invalid secure link.",
            ) from error
        if not isinstance(signed_path, str) or not signed_path.startswith("/"):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The storage service returned an invalid secure link.",
            )
        storage_path = (
            signed_path.lstrip("/")
            if signed_path.startswith("/storage/v1/")
            else f"storage/v1/{signed_path.lstrip('/')}"
        )
        return urljoin(f"{self.settings.supabase_url}/", storage_path)
