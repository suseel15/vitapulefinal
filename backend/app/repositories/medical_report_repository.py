from typing import Any
from uuid import UUID

from app.repositories.supabase import SupabaseRepository


class MedicalReportRepository:
    def __init__(self, client: SupabaseRepository, athlete_id: UUID) -> None:
        self.client = client
        self.athlete_id = str(athlete_id)

    async def list(self) -> list[dict[str, Any]]:
        rows = await self.client.rest(
            "GET",
            "medical_reports",
            params={
                "athlete_id": f"eq.{self.athlete_id}",
                "select": "*",
                "order": "uploaded_at.desc",
            },
        )
        return rows if isinstance(rows, list) else []

    async def get(self, report_id: UUID) -> dict[str, Any] | None:
        rows = await self.client.rest(
            "GET",
            "medical_reports",
            params={
                "id": f"eq.{report_id}",
                "athlete_id": f"eq.{self.athlete_id}",
                "select": "*",
                "limit": "1",
            },
        )
        return rows[0] if isinstance(rows, list) and rows else None

    async def find_by_hash(self, file_sha256: str) -> dict[str, Any] | None:
        rows = await self.client.rest(
            "GET",
            "medical_reports",
            params={
                "athlete_id": f"eq.{self.athlete_id}",
                "file_sha256": f"eq.{file_sha256}",
                "select": "id,original_filename,report_date,uploaded_at",
                "limit": "1",
            },
        )
        return rows[0] if isinstance(rows, list) and rows else None

    async def create(self, report: dict[str, Any]) -> dict[str, Any]:
        rows = await self.client.rest(
            "POST",
            "medical_reports",
            payload={**report, "athlete_id": self.athlete_id},
            prefer="return=representation",
        )
        return rows[0]

    async def update(self, report_id: UUID, changes: dict[str, Any]) -> None:
        await self.client.rest(
            "PATCH",
            "medical_reports",
            params={"id": f"eq.{report_id}", "athlete_id": f"eq.{self.athlete_id}"},
            payload=changes,
        )

    async def insert_pages(self, pages: list[dict[str, Any]]) -> None:
        if not pages:
            return
        await self.client.rest("POST", "medical_report_pages", payload=pages)

    async def insert_findings(self, findings: list[dict[str, Any]]) -> None:
        if not findings:
            return
        await self.client.rest("POST", "medical_report_findings", payload=findings)

    async def delete_pages(self, report_id: UUID) -> None:
        await self.client.rest(
            "DELETE",
            "medical_report_pages",
            params={"medical_report_id": f"eq.{report_id}", "athlete_id": f"eq.{self.athlete_id}"},
        )

    async def delete(self, report_id: UUID) -> None:
        await self.client.rest(
            "DELETE",
            "medical_reports",
            params={"id": f"eq.{report_id}", "athlete_id": f"eq.{self.athlete_id}"},
        )
