from typing import Any
from uuid import UUID

from app.repositories.supabase import SupabaseRepository


class BodyMapRepository:
    def __init__(self, client: SupabaseRepository, athlete_id: UUID) -> None:
        self.client = client
        self.athlete_id = str(athlete_id)

    async def regions(self) -> list[dict[str, Any]]:
        rows = await self.client.rest(
            "GET",
            "body_regions",
            params={"select": "*", "order": "display_order.asc"},
        )
        return rows if isinstance(rows, list) else []

    async def findings(self) -> list[dict[str, Any]]:
        rows = await self.client.rest(
            "GET",
            "body_region_findings",
            params={
                "athlete_id": f"eq.{self.athlete_id}",
                "select": "*",
                "order": "created_at.desc",
            },
        )
        return rows if isinstance(rows, list) else []

    async def insert_findings(self, findings: list[dict[str, Any]]) -> None:
        if findings:
            await self.client.rest("POST", "body_region_findings", payload=findings)
