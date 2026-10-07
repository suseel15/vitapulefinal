from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1 import connect as connect_api
from app.api.v1.health import athlete_context
from app.main import app
from app.repositories import connect_repository
from app.repositories.connect_repository import ConnectRepository, _normalized_values
from app.schemas.health_data_sync import (
    HealthConnectSyncRequest,
    HealthDataRecordCreate,
    HealthDataType,
)

client = TestClient(app)
ATHLETE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


def test_connect_and_health_data_routes_require_an_authenticated_athlete() -> None:
    paths = (
        "/api/v1/connect/status",
        "/api/v1/connect/devices",
        "/api/v1/connect/sync/history",
        "/api/v1/health-data/sleep",
        "/api/v1/health-data/heart-rate",
        "/api/v1/health-data/activity",
        "/api/v1/health-data/exercise",
        "/api/v1/health-data/spo2",
    )
    for path in paths:
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.json()["success"] is False


def test_health_connect_sync_accepts_camel_case_aliases_and_utc_times() -> None:
    start = datetime.now(UTC) - timedelta(hours=12)
    end = start + timedelta(hours=8)
    request = HealthConnectSyncRequest.model_validate(
        {
            "sources": ["HEALTH_CONNECT"],
            "dataTypes": ["SLEEP"],
            "from": start.isoformat(),
            "to": end.isoformat(),
            "records": [
                {
                    "dataType": "SLEEP",
                    "sourceRecordId": "record-123",
                    "sourceApplication": "com.example.health",
                    "startTime": start.isoformat(),
                    "endTime": end.isoformat(),
                    "value": {"duration_minutes": 480},
                }
            ],
        }
    )

    assert request.records[0].data_type == HealthDataType.SLEEP
    assert request.records[0].value == {"duration_minutes": 480}


def test_health_connect_sync_rejects_client_supplied_athlete_and_oversized_range() -> None:
    start = datetime.now(UTC) - timedelta(days=31)
    end = datetime.now(UTC)
    body = {
        "sources": ["HEALTH_CONNECT"],
        "dataTypes": ["STEPS"],
        "from": start.isoformat(),
        "to": end.isoformat(),
        "athleteId": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    }
    with pytest.raises(ValidationError):
        HealthConnectSyncRequest.model_validate(body)
    body.pop("athleteId")
    with pytest.raises(ValidationError, match="limited to 30 days"):
        HealthConnectSyncRequest.model_validate(body)


@pytest.mark.parametrize(
    "value",
    (
        {"average_bpm": True, "sample_count": 1},
        {"average_bpm": float("nan"), "sample_count": 1},
        {"average_bpm": 72, "sample_count": 1, "samples": [72]},
    ),
)
def test_health_connect_upload_rejects_invalid_or_raw_heart_rate_values(value: dict) -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        HealthDataRecordCreate.model_validate(
            {
                "dataType": "HEART_RATE",
                "sourceRecordId": "hr-record-1",
                "sourceApplication": "com.example.health",
                "startTime": now.isoformat(),
                "endTime": now.isoformat(),
                "value": value,
            }
        )


def test_health_connect_records_are_normalized_without_raw_samples() -> None:
    now = datetime.now(UTC)
    record = HealthDataRecordCreate.model_validate(
        {
            "dataType": "HEART_RATE",
            "sourceRecordId": "hr-record-1",
            "sourceApplication": "com.example.health",
            "startTime": now.isoformat(),
            "endTime": now.isoformat(),
            "value": {"average_bpm": 73.5, "sample_count": 8, "measurement_type": "GENERAL"},
        }
    )

    saved = _normalized_values(record, now)
    assert saved["average_bpm"] == 73.5
    assert saved["sample_count"] == 8
    assert "samples" not in saved


@pytest.mark.asyncio
async def test_sync_repository_scopes_records_and_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    saved_rows: dict[tuple[str, str], dict] = {}
    audit_events: list[str] = []

    class FakeHealthRepository:
        athlete_id = str(ATHLETE_ID)

        def __init__(self, _client: object, _athlete_id: UUID) -> None:
            self.client = self

        async def list_rows(self, table: str, **kwargs: object) -> list[dict]:
            source_ids = []
            filters = kwargs.get("filters")
            if isinstance(filters, dict) and "source_record_id" in filters:
                expression = filters["source_record_id"]
                source_ids = expression[4:-1].split(",")
            return [
                {"source_record_id": source_id}
                for source_id in source_ids
                if (table, source_id) in saved_rows
            ]

        async def upsert(self, table: str, values: dict, *, conflict: str) -> dict:
            scoped_values = {**values, "athlete_id": self.athlete_id}
            key = (table, scoped_values.get("source_record_id", scoped_values.get("id", "")))
            saved_rows[key] = scoped_values
            return {**scoped_values, "id": values.get("id", str(UUID(int=len(saved_rows) + 1)))}

        async def upsert_many(self, table: str, values: list[dict], *, conflict: str) -> list[dict]:
            return [await self.upsert(table, value, conflict=conflict) for value in values]

        async def rest(self, method: str, table: str, *, payload: dict, **_kwargs: object) -> None:
            assert method == "POST"
            assert table == "connect_audit_events"
            assert payload["athlete_id"] == str(ATHLETE_ID)
            audit_events.append(payload["event_type"])

    monkeypatch.setattr(connect_repository, "HealthRepository", FakeHealthRepository)
    start = datetime.now(UTC) - timedelta(minutes=2)
    end = datetime.now(UTC) - timedelta(minutes=1)
    request = HealthConnectSyncRequest.model_validate(
        {
            "sources": ["HEALTH_CONNECT"],
            "dataTypes": ["STEPS"],
            "from": start.isoformat(),
            "to": end.isoformat(),
            "records": [
                {
                    "dataType": "STEPS",
                    "sourceRecordId": "step-1",
                    "sourceApplication": "com.example.health",
                    "startTime": start.isoformat(),
                    "endTime": end.isoformat(),
                    "value": {"count": 120},
                },
                {
                    "dataType": "STEPS",
                    "sourceRecordId": "step-1",
                    "sourceApplication": "com.example.health",
                    "startTime": start.isoformat(),
                    "endTime": end.isoformat(),
                    "value": {"count": 120},
                },
            ],
        }
    )

    first = await ConnectRepository(object(), ATHLETE_ID).save_sync(request)
    second = await ConnectRepository(object(), ATHLETE_ID).save_sync(request)

    assert first["records_imported"] == 1
    assert first["records_skipped"] == 1
    assert second["records_imported"] == 0
    assert second["records_skipped"] == 2
    assert audit_events.count("HEALTH_DATA_SYNC_COMPLETED") == 2


def test_connect_sync_endpoint_uses_athlete_scoped_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    class Repository:
        async def save_sync(self, _request: HealthConnectSyncRequest) -> dict:
            return {"run": {"status": "SYNCED"}, "records_imported": 1, "records_skipped": 0}

    async def fake_context() -> tuple:
        return ATHLETE_ID, object(), object()

    app.dependency_overrides[athlete_context] = fake_context
    monkeypatch.setattr(connect_api, "_repo", lambda _context: Repository())
    try:
        response = client.post(
            "/api/v1/connect/sync",
            json={
                "sources": ["HEALTH_CONNECT"],
                "dataTypes": ["STEPS"],
                "from": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
                "to": datetime.now(UTC).isoformat(),
                "records": [],
            },
            headers={"Authorization": "Bearer test-token"},
        )
    finally:
        app.dependency_overrides.pop(athlete_context, None)

    assert response.status_code == 200
    assert response.json()["data"]["records_imported"] == 1
