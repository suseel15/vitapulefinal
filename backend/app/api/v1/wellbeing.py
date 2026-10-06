from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.v1.health import AthleteContext, athlete_context
from app.core.responses import success
from app.repositories.wellbeing_repository import WellbeingRepository
from app.schemas.wellbeing import (
    CameraFeaturesCreate,
    CameraSessionCreate,
    CheckInCreate,
    RecoveryRecordCreate,
    SleepRecordCreate,
    WellbeingReportCreate,
)
from app.services.wellbeing_service import classify_trend, interpret_wellbeing, recovery_state

router = APIRouter(prefix="/wellbeing", tags=["wellbeing"])


def _repo(context: AthleteContext) -> WellbeingRepository:
    return WellbeingRepository(context[2], context[0])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The requested wellbeing record was not found.")


@router.get("/overview")
async def overview(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    repository = _repo(context)
    checkins, cameras, sleeps, recoveries = await _gather(
        repository.list("wellbeing_checkins", limit=1),
        repository.list("camera_wellbeing_sessions", limit=1),
        repository.list("sleep_records", limit=1),
        repository.list("recovery_records", limit=1),
    )
    latest_checkin = checkins[0] if checkins else None
    latest_sleep = sleeps[0] if sleeps else None
    latest_recovery = recoveries[0] if recoveries else None
    recovery_context = latest_recovery
    if latest_recovery is None:
        derived_state, factors = recovery_state(latest_checkin, latest_sleep)
        if factors:
            recovery_context = {
                "recovery_state": derived_state,
                "supporting_factors": factors,
                "calculation_version": "recovery-context-v1",
                "source": "CALCULATED",
            }
    latest_camera_features = (
        await repository.list(
            "camera_wellbeing_features",
            limit=1,
            filters={"session_id": f"eq.{cameras[0]['id']}"},
        )
        if cameras
        else []
    )
    return success(
        request,
        {
            "checkin": latest_checkin,
            "camera_session": cameras[0] if cameras else None,
            "sleep": latest_sleep,
            "recovery": latest_recovery,
            "recovery_context": recovery_context,
            "camera_features": latest_camera_features[0] if latest_camera_features else None,
            "context": interpret_wellbeing(
                latest_checkin,
                latest_camera_features[0] if latest_camera_features else None,
                latest_sleep,
                recovery_context,
            ),
        },
    )


@router.get("/checkins")
async def list_checkins(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    return success(request, {"checkins": await _repo(context).list("wellbeing_checkins")})


@router.post("/checkins", status_code=status.HTTP_201_CREATED)
async def create_checkin(
    request: Request,
    body: CheckInCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    result = await _repo(context).upsert(
        "wellbeing_checkins",
        body.model_dump(mode="json", exclude_none=True),
        conflict="athlete_id,id",
    )
    return success(request, {"checkin": result})


@router.get("/checkins/{record_id}")
async def get_checkin(
    request: Request,
    record_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    record = await _repo(context).get("wellbeing_checkins", record_id)
    if record is None:
        raise _not_found()
    return success(request, {"checkin": record})


@router.get("/camera/sessions")
async def list_camera_sessions(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    return success(request, {"sessions": await _repo(context).list("camera_wellbeing_sessions")})


@router.post("/camera/sessions", status_code=status.HTTP_201_CREATED)
async def create_camera_session(
    request: Request,
    body: CameraSessionCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    record = await _repo(context).upsert(
        "camera_wellbeing_sessions",
        body.model_dump(mode="json", exclude_none=True),
        conflict="athlete_id,id",
    )
    return success(request, {"session": record})


@router.get("/camera/sessions/{session_id}")
async def get_camera_session(
    request: Request,
    session_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    record = await _repo(context).get("camera_wellbeing_sessions", session_id)
    if record is None:
        raise _not_found()
    return success(request, {"session": record})


@router.post("/camera/sessions/{session_id}/features", status_code=status.HTTP_201_CREATED)
async def create_camera_features(
    request: Request,
    session_id: UUID,
    body: CameraFeaturesCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    repository = _repo(context)
    if await repository.get("camera_wellbeing_sessions", session_id) is None:
        raise _not_found()
    result = await repository.insert_features(session_id, body.model_dump(mode="json", exclude_none=True))
    return success(request, {"features": result})


@router.get("/camera/sessions/{session_id}/features")
async def get_camera_features(
    request: Request,
    session_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    repository = _repo(context)
    if await repository.get("camera_wellbeing_sessions", session_id) is None:
        raise _not_found()
    features = await repository.list(
        "camera_wellbeing_features",
        limit=1,
        filters={"session_id": f"eq.{session_id}"},
    )
    if not features:
        raise _not_found()
    return success(request, {"features": features[0]})


@router.get("/sleep")
async def list_sleep_records(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    return success(request, {"sleep_records": await _repo(context).list("sleep_records")})


@router.post("/sleep", status_code=status.HTTP_201_CREATED)
async def create_sleep_record(
    request: Request,
    body: SleepRecordCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    record = await _repo(context).upsert(
        "sleep_records",
        body.model_dump(mode="json", exclude_none=True),
        conflict="athlete_id,id",
    )
    return success(request, {"sleep_record": record})


@router.get("/recovery")
async def list_recovery(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    return success(request, {"recovery_records": await _repo(context).list("recovery_records")})


@router.post("/recovery", status_code=status.HTTP_201_CREATED)
async def create_recovery(
    request: Request,
    body: RecoveryRecordCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    record = await _repo(context).upsert(
        "recovery_records",
        body.model_dump(mode="json"),
        conflict="athlete_id,date",
    )
    return success(request, {"recovery_record": record})


@router.get("/history")
async def history(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    repository = _repo(context)
    tables = (
        ("CHECK_IN", "wellbeing_checkins"),
        ("CAMERA", "camera_wellbeing_sessions"),
        ("SLEEP", "sleep_records"),
        ("RECOVERY", "recovery_records"),
        ("REPORT", "wellbeing_reports"),
    )
    grouped = await _gather(*(repository.list(table) for _, table in tables))
    items = [
        {"type": kind, "record": record, "created_at": record.get("created_at")}
        for (kind, _), records in zip(tables, grouped, strict=True)
        for record in records
    ]
    items.sort(key=lambda item: item["created_at"] or "", reverse=True)
    return success(request, {"items": items[:300]})


@router.get("/trends")
async def trends(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    checkins, sleeps, recoveries, cameras = await _gather(
        _repo(context).list("wellbeing_checkins", limit=90, order="created_at.asc"),
        _repo(context).list("sleep_records", limit=90, order="created_at.asc"),
        _repo(context).list("recovery_records", limit=90, order="created_at.asc"),
        _repo(context).list("camera_wellbeing_features", limit=90, order="created_at.asc"),
    )
    fields = ("energy", "stress", "fatigue", "soreness", "recovery_feeling")
    series = {
        field: {
            "values": [record[field] for record in checkins if isinstance(record.get(field), int)],
            "source": "SELF_REPORTED",
            "higher_is_better": field not in {"stress", "fatigue", "soreness"},
        }
        for field in fields
    }
    series["sleep_duration_minutes"] = {
        "values": [record["duration_minutes"] for record in sleeps if isinstance(record.get("duration_minutes"), int)],
        "sources": sorted({record.get("source", "SELF_REPORTED") for record in sleeps}),
        "higher_is_better": True,
    }
    series["recovery_state"] = {
        "values": [record["recovery_state"] for record in recoveries],
        "source": "CALCULATED",
    }
    series["camera_capture_quality"] = {
        "values": [record["capture_quality"] for record in cameras],
        "source": "CAMERA_OBSERVED",
    }
    for key, value in series.items():
        if key not in {"recovery_state", "camera_capture_quality"}:
            value["trend"] = classify_trend(
                [float(item) for item in value["values"]],
                higher_is_better=value.get("higher_is_better", True),
            )
    return success(request, {"series": series})


@router.post("/reports", status_code=status.HTTP_201_CREATED)
async def create_report(
    request: Request,
    body: WellbeingReportCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    record = await _repo(context).upsert(
        "wellbeing_reports",
        body.model_dump(mode="json", exclude_none=True),
        conflict="athlete_id,id",
    )
    return success(request, {"report": record})


@router.get("/reports")
async def list_reports(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    return success(request, {"reports": await _repo(context).list("wellbeing_reports")})


async def _gather(*coroutines: Any) -> list[Any]:
    import asyncio

    return list(await asyncio.gather(*coroutines))
