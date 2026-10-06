from typing import Any
from uuid import UUID

from app.repositories.supabase import SupabaseRepository


class BiomarkerRepository:
    def __init__(self, client: SupabaseRepository, athlete_id: UUID) -> None:
        self.client = client
        self.athlete_id = str(athlete_id)

    async def list_measurements(self, medical_report_id: UUID | None = None) -> list[dict[str, Any]]:
        params = {
            "athlete_id": f"eq.{self.athlete_id}",
            "select": "*",
            "order": "collection_date.desc.nullslast,created_at.desc",
        }
        if medical_report_id:
            params["medical_report_id"] = f"eq.{medical_report_id}"
        rows = await self.client.rest("GET", "biomarker_measurements", params=params)
        return rows if isinstance(rows, list) else []

    async def insert_measurements(self, measurements: list[dict[str, Any]]) -> None:
        if measurements:
            await self.client.rest("POST", "biomarker_measurements", payload=measurements)
