from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.repositories.health_repository import HealthRepository
from app.repositories.supabase import SupabaseRepository
from app.schemas.health_data_sync import (
    ConnectedDeviceCreate,
    HealthConnectPermissionCreate,
    HealthConnectSyncRequest,
    HealthDataRecordCreate,
    HealthDataType,
    HealthSyncRunCreate,
)

HEALTH_TABLES = {
    HealthDataType.SLEEP: "unified_sleep_records",
    HealthDataType.HEART_RATE: "unified_heart_rate_records",
    HealthDataType.STEPS: "unified_activity_records",
    HealthDataType.EXERCISE: "unified_exercise_records",
    HealthDataType.OXYGEN_SATURATION: "unified_oxygen_saturation_records",
}


class ConnectRepository:
    def __init__(self, client: SupabaseRepository, athlete_id: UUID) -> None:
        self.rows = HealthRepository(client, athlete_id)
        self.athlete_id = athlete_id

    async def list(self, table: str, *, limit: int = 100, order: str = "created_at.desc") -> list[dict[str, Any]]:
        return await self.rows.list_rows(table, limit=limit, order=order)

    async def upsert_device(self, device: ConnectedDeviceCreate) -> dict[str, Any]:
        values = device.model_dump(mode="json", exclude_none=True)
        if device.status == "CONNECTED":
            values["last_seen"] = datetime.now(UTC).isoformat()
        result = await self.rows.upsert(
            "connected_devices",
            values,
            conflict="athlete_id,identifier",
        )
        if device.status in {"CONNECTED", "DISCONNECTED"}:
            await self._audit(
                f"DEVICE_{device.status}",
                "connected_device",
                UUID(result["id"]),
            )
        return result

    async def save_permission(self, permission: HealthConnectPermissionCreate) -> dict[str, Any]:
        previous = await self.rows.list_rows(
            "health_data_permissions",
            select="id,permission_state",
            limit=1,
            filters={
                "source": "eq.HEALTH_CONNECT",
                "data_type": f"eq.{permission.data_type.value}",
            },
        )
        values = permission.model_dump(mode="json", exclude_none=True)
        values["source"] = "HEALTH_CONNECT"
        result = await self.rows.upsert(
            "health_data_permissions",
            values,
            conflict="athlete_id,source,data_type",
        )
        previously_granted = bool(previous and previous[0]["permission_state"] == "GRANTED")
        if permission.permission_state == "GRANTED" and not previously_granted:
            await self._audit("HEALTH_CONNECT_PERMISSION_GRANTED", "health_data_permission", UUID(result["id"]))
        elif permission.permission_state in {"DENIED", "REVOKED"} and previously_granted:
            await self._audit("HEALTH_CONNECT_PERMISSION_REVOKED", "health_data_permission", UUID(result["id"]))
        return result

    async def save_sync(self, request: HealthConnectSyncRequest) -> dict[str, Any]:
        now = datetime.now(UTC)
        run = request.sync_run
        run_id = run.id if run and run.id else uuid4()
        await self._audit("HEALTH_DATA_SYNC_STARTED", "health_data_sync_run", run_id)

        accepted = 0
        duplicate_count = 0
        counts: dict[HealthDataType, tuple[int, int]] = {}
        seen: set[tuple[HealthDataType, str]] = set()
        table_records: dict[HealthDataType, list[HealthDataRecordCreate]] = {}
        for record in request.records:
            identity = (record.data_type, record.source_record_id)
            if identity in seen:
                duplicate_count += 1
                continue
            seen.add(identity)
            table_records.setdefault(record.data_type, []).append(record)

        for data_type, records in table_records.items():
            table = HEALTH_TABLES[data_type]
            existing_ids: set[str] = set()
            new_count = 0
            type_duplicates = 0
            for offset in range(0, len(records), 100):
                query_batch = records[offset : offset + 100]
                identifiers = ",".join(record.source_record_id for record in query_batch)
                existing = await self.rows.list_rows(
                    table,
                    select="source_record_id",
                    limit=len(query_batch),
                    filters={"source": "eq.HEALTH_CONNECT", "source_record_id": f"in.({identifiers})"},
                )
                batch_existing_ids = {row["source_record_id"] for row in existing}
                new_count += sum(record.source_record_id not in batch_existing_ids for record in query_batch)
                type_duplicates += sum(record.source_record_id in batch_existing_ids for record in query_batch)
                await self.rows.upsert_many(
                    table,
                    [_normalized_values(record, now) for record in query_batch],
                    conflict="athlete_id,source,source_record_id",
                )
            accepted += new_count
            duplicate_count += type_duplicates
            counts[data_type] = (new_count, type_duplicates)

        persisted_run = _sync_run_values(request, run, run_id, now, accepted, duplicate_count)
        saved_run = await self.rows.upsert(
            "health_data_sync_runs",
            persisted_run,
            conflict="athlete_id,id",
        )
        for data_type in request.data_types:
            imported, skipped = counts.get(data_type, (0, 0))
            await self.rows.upsert(
                "health_data_sync_sources",
                {
                    "sync_run_id": str(run_id),
                    "source": "HEALTH_CONNECT",
                    "data_type": data_type.value,
                    "range_start": request.from_time.isoformat(),
                    "range_end": request.to_time.isoformat(),
                    "records_imported": imported,
                    "records_skipped": skipped,
                },
                conflict="athlete_id,sync_run_id,data_type",
            )
        await self._audit("HEALTH_DATA_SYNC_COMPLETED", "health_data_sync_run", run_id)
        return {
            "run": saved_run,
            "records_imported": accepted,
            "records_skipped": duplicate_count,
        }

    async def delete_health_data(self) -> None:
        filters = {"athlete_id": f"eq.{self.rows.athlete_id}"}
        source_filters = {**filters, "source": "eq.HEALTH_CONNECT"}
        await self.rows.client.rest("DELETE", "health_data_sync_sources", params=source_filters)
        await self.rows.client.rest("DELETE", "health_data_sync_runs", params=source_filters)
        await self.rows.client.rest(
            "DELETE",
            "health_data_permissions",
            params=source_filters,
        )
        await self.rows.client.rest(
            "DELETE",
            "wearable_connections",
            params={**filters, "provider": "eq.HEALTH_CONNECT"},
        )
        for table in HEALTH_TABLES.values():
            await self.rows.client.rest("DELETE", table, params=source_filters)
        await self._audit("HEALTH_DATA_DELETED", "health_connect_data", None)

    async def _audit(self, event_type: str, resource_type: str, resource_id: UUID | None) -> None:
        await self.rows.client.rest(
            "POST",
            "connect_audit_events",
            payload={
                "athlete_id": str(self.athlete_id),
                "actor_id": str(self.athlete_id),
                "event_type": event_type,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
            },
        )


def _normalized_values(record: HealthDataRecordCreate, now: datetime) -> dict[str, Any]:
    values = record.value
    common: dict[str, Any] = {
        "source": "HEALTH_CONNECT",
        "source_record_id": record.source_record_id,
        "source_application": record.source_application,
        "start_time": record.start_time.isoformat(),
        "end_time": record.end_time.isoformat(),
        "last_modified_at": (record.last_modified_at or now).isoformat(),
    }
    match record.data_type:
        case HealthDataType.SLEEP:
            common["duration_minutes"] = values["duration_minutes"]
        case HealthDataType.HEART_RATE:
            common.update(
                average_bpm=values["average_bpm"],
                sample_count=values["sample_count"],
                measurement_type=values.get("measurement_type", "UNKNOWN"),
            )
        case HealthDataType.STEPS:
            common["count"] = values["count"]
        case HealthDataType.EXERCISE:
            common.update(
                exercise_type=values["exercise_type"],
                duration_minutes=values["duration_minutes"],
                title=values.get("title"),
            )
        case HealthDataType.OXYGEN_SATURATION:
            common["percentage"] = values["percentage"]
    return common


def _sync_run_values(
    request: HealthConnectSyncRequest,
    run: HealthSyncRunCreate | None,
    run_id: UUID,
    now: datetime,
    imported: int,
    skipped: int,
) -> dict[str, Any]:
    if run is not None:
        return {
            **run.model_dump(mode="json", exclude={"id"}, exclude_none=True),
            "id": str(run_id),
            "source": "HEALTH_CONNECT",
            "records_imported": imported,
            "records_skipped": skipped,
        }
    return {
        "id": str(run_id),
        "source": "HEALTH_CONNECT",
        "started_at": now.isoformat(),
        "completed_at": now.isoformat(),
        "status": "NO_DATA" if not request.records else "SYNCED",
        "records_found": len(request.records),
        "records_imported": imported,
        "records_skipped": skipped,
        "records_failed": 0,
        "data_types": [data_type.value for data_type in request.data_types],
    }
