from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.v1.health import AthleteContext, athlete_context
from app.core.responses import success
from app.repositories.health_repository import HealthRepository
from app.schemas.device import DeviceRegistrationCreate, DeviceUpdate

router = APIRouter(prefix="/devices", tags=["devices"])


def _repository(context: AthleteContext) -> HealthRepository:
    return HealthRepository(context[2], context[0])


def _device_response(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "device_identifier": record["device_identifier"],
        "device_type": record["device_type"],
        "sensor_type": record["sensor_type"],
        "transport": record["transport"],
        "ip": record["ip_address"],
        "firmware_protocol": record["firmware_protocol"],
        "is_active": record["is_active"],
        "last_seen_at": record.get("last_seen_at"),
    }


async def _owned_device(context: AthleteContext, device_id: UUID) -> dict[str, Any]:
    records = await _repository(context).list_rows(
        "movement_devices",
        filters={"id": f"eq.{device_id}"},
        limit=1,
    )
    if not records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The requested device was not found.")
    return records[0]


@router.get("")
async def list_devices(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    devices = await _repository(context).list_rows("movement_devices", order="created_at.desc", limit=100)
    return success(request, {"devices": [_device_response(device) for device in devices]})


@router.post("", status_code=status.HTTP_201_CREATED)
async def register_device(
    request: Request,
    body: DeviceRegistrationCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    record = await _repository(context).upsert(
        "movement_devices",
        {
            "device_identifier": body.device_identifier,
            "device_type": body.device_type,
            "sensor_type": body.sensor_type,
            "transport": body.transport,
            "ip_address": str(body.ip),
            "firmware_protocol": body.firmware_protocol,
            "is_active": True,
        },
        conflict="athlete_id,device_identifier",
    )
    return success(request, {"device": _device_response(record)})


@router.get("/{device_id}")
async def get_device(
    request: Request,
    device_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    return success(request, {"device": _device_response(await _owned_device(context, device_id))})


@router.patch("/{device_id}")
async def update_device(
    request: Request,
    device_id: UUID,
    body: DeviceUpdate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    await _owned_device(context, device_id)
    updated = await _repository(context).patch("movement_devices", device_id, body.model_dump())
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The requested device was not found.")
    return success(request, {"device": _device_response(updated)})
