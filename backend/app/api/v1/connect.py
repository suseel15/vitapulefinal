from asyncio import gather
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.api.v1.health import AthleteContext, athlete_context
from app.core.responses import success
from app.repositories.connect_repository import ConnectRepository, HEALTH_TABLES
from app.schemas.health_data_sync import (
    ConnectedDeviceCreate,
    HealthConnectPermissionCreate,
    HealthConnectSyncRequest,
    HealthDataType,
)

router = APIRouter(tags=["connect"])


def _repo(context: AthleteContext) -> ConnectRepository:
    athlete_id, _, client = context
    return ConnectRepository(client, athlete_id)


@router.get("/connect/status")
async def connect_status(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict[str, Any]:
    repository = _repo(context)
    devices, wearable, permissions, runs = await gather(
        repository.list("connected_devices", limit=50, order="updated_at.desc"),
        repository.list("wearable_connections", limit=10, order="updated_at.desc"),
        repository.list("health_data_permissions", limit=5, order="checked_at.desc"),
        repository.list("health_data_sync_runs", limit=1, order="started_at.desc"),
    )
    movement = next(
        (device for device in devices if device.get("device_type") in {"ESP32", "MPU6050"}),
        None,
    )
    latest_run = runs[0] if runs else None
    authorized_types = sorted(
        permission["data_type"]
        for permission in permissions
        if permission["permission_state"] == "GRANTED"
    )
    return success(
        request,
        {
            "movement_device": movement or {"status": "NOT_CONNECTED"},
            "wearable": wearable[0] if wearable else {"status": "UNKNOWN"},
            "health_connect": {
                "status": "AUTHORIZED" if authorized_types else (
                    "PERMISSION_REQUIRED" if permissions else "NOT_CONFIGURED"
                ),
                "authorized_data_types": authorized_types,
                "last_sync_at": latest_run.get("completed_at") if latest_run else None,
                "last_sync_status": latest_run.get("status") if latest_run else None,
            },
        },
    )


@router.get("/connect/devices")
async def list_connected_devices(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict[str, Any]:
    return success(request, {"devices": await _repo(context).list("connected_devices", limit=100)})


@router.post("/connect/devices", status_code=201)
async def upsert_connected_device(
    request: Request,
    body: ConnectedDeviceCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict[str, Any]:
    device = await _repo(context).upsert_device(body)
    return success(request, {"device": device})


@router.post("/connect/permissions", status_code=201)
async def save_health_connect_permission(
    request: Request,
    body: HealthConnectPermissionCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict[str, Any]:
    permission = await _repo(context).save_permission(body)
    return success(request, {"permission": permission})


@router.post("/connect/sync")
async def synchronize_health_data(
    request: Request,
    body: HealthConnectSyncRequest,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict[str, Any]:
    result = await _repo(context).save_sync(body)
    return success(request, result)


@router.delete("/connect/health-data")
async def delete_health_connect_data(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict[str, Any]:
    await _repo(context).delete_health_data()
    return success(request, {"deleted": True, "scope": "HEALTH_CONNECT_ACCOUNT_DATA"})


@router.get("/connect/sync/history")
async def health_sync_history(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    runs = await _repo(context).list("health_data_sync_runs", limit=limit, order="started_at.desc")
    return success(request, {"runs": runs})


async def _list_records(
    request: Request,
    context: AthleteContext,
    data_type: HealthDataType,
    limit: int,
) -> dict[str, Any]:
    table = HEALTH_TABLES[data_type]
    order = "start_time.desc"
    key = {
        HealthDataType.SLEEP: "sleep_records",
        HealthDataType.HEART_RATE: "heart_rate_records",
        HealthDataType.STEPS: "activity_records",
        HealthDataType.EXERCISE: "exercise_records",
        HealthDataType.OXYGEN_SATURATION: "spo2_records",
    }[data_type]
    return success(request, {key: await _repo(context).list(table, limit=limit, order=order)})


@router.get("/health-data/sleep")
async def health_data_sleep(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    return await _list_records(request, context, HealthDataType.SLEEP, limit)


@router.get("/health-data/heart-rate")
async def health_data_heart_rate(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    return await _list_records(request, context, HealthDataType.HEART_RATE, limit)


@router.get("/health-data/activity")
async def health_data_activity(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    return await _list_records(request, context, HealthDataType.STEPS, limit)


@router.get("/health-data/exercise")
async def health_data_exercise(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    return await _list_records(request, context, HealthDataType.EXERCISE, limit)


@router.get("/health-data/spo2")
async def health_data_spo2(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    return await _list_records(request, context, HealthDataType.OXYGEN_SATURATION, limit)
