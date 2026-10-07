from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.repositories.supabase import SupabaseRepository


class HealthRepository:
    def __init__(self, client: SupabaseRepository, athlete_id: UUID) -> None:
        self.client = client
        self.athlete_id = str(athlete_id)

    async def list_rows(
        self,
        table: str,
        *,
        select: str = "*",
        order: str = "created_at.desc",
        limit: int = 100,
        filters: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        params = {
            "athlete_id": f"eq.{self.athlete_id}",
            "select": select,
            "order": order,
            "limit": str(limit),
        }
        if filters:
            params.update(filters)
        rows = await self.client.rest(
            "GET",
            table,
            params=params,
        )
        return rows if isinstance(rows, list) else []

    async def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        rows = await self.client.rest(
            "POST",
            table,
            payload={**values, "athlete_id": self.athlete_id},
            prefer="return=representation",
        )
        return rows[0]

    async def upsert(
        self,
        table: str,
        values: dict[str, Any],
        *,
        conflict: str,
    ) -> dict[str, Any]:
        rows = await self.client.rest(
            "POST",
            table,
            params={"on_conflict": conflict},
            payload={**values, "athlete_id": self.athlete_id},
            prefer="resolution=merge-duplicates,return=representation",
        )
        return rows[0]

    async def upsert_many(
        self,
        table: str,
        values: list[dict[str, Any]],
        *,
        conflict: str,
    ) -> list[dict[str, Any]]:
        if not values:
            return []
        rows = await self.client.rest(
            "POST",
            table,
            params={"on_conflict": conflict},
            payload=[{**row, "athlete_id": self.athlete_id} for row in values],
            prefer="resolution=merge-duplicates,return=representation",
        )
        if not isinstance(rows, list) or len(rows) != len(values):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The health data service returned an incomplete batch response.",
            )
        return rows

    async def patch(self, table: str, row_id: UUID, values: dict[str, Any]) -> dict[str, Any] | None:
        rows = await self.client.rest(
            "PATCH",
            table,
            params={"id": f"eq.{row_id}", "athlete_id": f"eq.{self.athlete_id}", "select": "*"},
            payload=values,
            prefer="return=representation",
        )
        return rows[0] if isinstance(rows, list) and rows else None

    async def delete(self, table: str, row_id: UUID) -> None:
        await self.client.rest(
            "DELETE",
            table,
            params={"id": f"eq.{row_id}", "athlete_id": f"eq.{self.athlete_id}"},
        )
