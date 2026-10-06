from typing import Any
from uuid import UUID

from app.repositories.health_repository import HealthRepository
from app.repositories.supabase import SupabaseRepository


class WellbeingRepository:
    def __init__(self, client: SupabaseRepository, athlete_id: UUID) -> None:
        self.rows = HealthRepository(client, athlete_id)

    async def list(
        self,
        table: str,
        *,
        limit: int = 100,
        order: str = "created_at.desc",
        filters: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        return await self.rows.list_rows(table, limit=limit, order=order, filters=filters)

    async def get(self, table: str, record_id: UUID) -> dict[str, Any] | None:
        rows = await self.rows.list_rows(table, filters={"id": f"eq.{record_id}"}, limit=1)
        return rows[0] if rows else None

    async def insert(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = await self.rows.insert(table, payload)
        await self._audit(f"CREATE_{table.upper()}", table, result.get("id"))
        return result

    async def upsert(self, table: str, payload: dict[str, Any], *, conflict: str) -> dict[str, Any]:
        result = await self.rows.upsert(table, payload, conflict=conflict)
        await self._audit(f"UPSERT_{table.upper()}", table, result.get("id"))
        return result

    async def insert_features(self, session_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        rows = await self.rows.client.rest(
            "POST",
            "camera_wellbeing_features",
            params={"on_conflict": "athlete_id,session_id"},
            payload={**payload, "session_id": str(session_id), "athlete_id": self.rows.athlete_id},
            prefer="resolution=merge-duplicates,return=representation",
        )
        result = rows[0]
        await self._audit("UPSERT_CAMERA_WELLBEING_FEATURES", "camera_wellbeing_features", result.get("id"))
        return result

    async def _audit(self, event_type: str, resource_type: str, resource_id: Any) -> None:
        await self.rows.client.rest(
            "POST",
            "wellbeing_audit_events",
            payload={
                "athlete_id": self.rows.athlete_id,
                "actor_id": self.rows.athlete_id,
                "event_type": event_type,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
            },
        )
