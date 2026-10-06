from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.v1.health import AthleteContext, athlete_context
from app.core.config import Settings, get_settings
from app.core.responses import success
from app.ml.analysis import classify_progress
from app.repositories.health_repository import HealthRepository
from app.repositories.supabase import SupabaseRepository
from app.schemas.movement import SessionAnalysisRequest

router = APIRouter(prefix="/ml", tags=["movement intelligence"])


def _repo(context: AthleteContext) -> HealthRepository:
    return HealthRepository(context[2], context[0])


def _client(context: AthleteContext) -> SupabaseRepository:
    return context[2]


async def _rows(
    context: AthleteContext,
    table: str,
    *,
    filters: dict[str, str] | None = None,
    select: str = "*",
    order: str = "created_at.desc",
    limit: int = 100,
) -> list[dict[str, Any]]:
    return await _repo(context).list_rows(
        table,
        filters=filters,
        select=select,
        order=order,
        limit=limit,
    )


@router.get("/models")
async def list_models(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not settings.ml_enabled:
        return success(request, {"enabled": False, "models": []})
    records = await _client(context).rest(
        "GET",
        "movement_model_registry",
        params={
            "select": (
                "id,model_name,model_type,version,feature_schema_version,metrics,status,"
                "supported_exercises,minimum_sampling_rate_hz,recommended_sampling_rate_hz,"
                "sensor_type,supported_sensor_placements,created_at"
            ),
            "status": "eq.ACTIVE",
            "order": "created_at.desc",
            "limit": "100",
        },
    )
    return success(request, {"enabled": True, "models": records if isinstance(records, list) else []})


@router.get("/models/{model_id}")
async def get_model(
    request: Request,
    model_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not settings.ml_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The requested model is unavailable.")
    records = await _client(context).rest(
        "GET",
        "movement_model_registry",
        params={
            "id": f"eq.{model_id}",
            "status": "eq.ACTIVE",
            "select": (
                "id,model_name,model_type,version,feature_schema_version,metrics,status,"
                "supported_exercises,minimum_sampling_rate_hz,recommended_sampling_rate_hz,"
                "sensor_type,supported_sensor_placements,created_at"
            ),
            "limit": "1",
        },
    )
    if not records:
        raise HTTPException(status_code=404, detail="The requested model was not found.")
    return success(request, {"model": records[0]})


@router.get("/models/{model_id}/artifact")
async def download_model_artifact(
    request: Request,
    model_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    if not settings.ml_enabled or not settings.ml_local_inference_enabled:
        raise HTTPException(status_code=404, detail="Local movement models are not enabled.")
    records = await _client(context).rest(
        "GET",
        "movement_model_registry",
        params={
            "id": f"eq.{model_id}",
            "status": "eq.ACTIVE",
            "select": "artifact_path,artifact_sha256,version,feature_schema_version",
            "limit": "1",
        },
    )
    if not records:
        raise HTTPException(status_code=404, detail="The requested model was not found.")
    model = records[0]
    root = settings.ml_model_directory.resolve()
    artifact_path = (root / str(model["artifact_path"])).resolve()
    if not artifact_path.is_relative_to(root) or not artifact_path.is_file():
        raise HTTPException(status_code=404, detail="The requested model artifact is unavailable.")
    contents = artifact_path.read_bytes()
    checksum = hashlib.sha256(contents).hexdigest()
    if checksum != model["artifact_sha256"]:
        raise HTTPException(status_code=503, detail="The registered model artifact failed integrity verification.")
    artifact_text = contents.decode("utf-8")
    artifact = json.loads(artifact_text)
    if (
        artifact.get("status") != "ACTIVE"
        or artifact.get("model_version") != model["version"]
        or artifact.get("feature_schema_version") != model["feature_schema_version"]
    ):
        raise HTTPException(status_code=503, detail="The registered model metadata does not match its artifact.")
    return success(request, {"artifact": artifact_text, "sha256": checksum})


@router.post("/analyze-session")
async def analyze_session(
    request: Request,
    body: SessionAnalysisRequest,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict[str, Any]:
    sessions = await _rows(context, "rehab_sessions", filters={"id": f"eq.{body.session_id}"}, limit=1)
    if not sessions:
        raise HTTPException(status_code=404, detail="The requested rehabilitation session was not found.")
    session = sessions[0]
    if session.get("status") != "COMPLETED":
        raise HTTPException(status_code=409, detail="Historical movement analysis requires a completed session.")
    session_id = str(body.session_id)
    repetitions = await _rows(
        context, "rehab_repetitions", filters={"session_id": f"eq.{session_id}"},
        order="rep_number.asc", limit=200,
    )
    quality_rows = await _rows(
        context, "movement_quality_results", filters={"session_id": f"eq.{session_id}"}, limit=1,
    )
    anomalies = await _rows(
        context, "movement_anomaly_results", filters={"session_id": f"eq.{session_id}"},
        order="event_timestamp.asc", limit=100,
    )
    fatigue_rows = await _rows(
        context, "movement_fatigue_results", filters={"session_id": f"eq.{session_id}"}, limit=1,
    )
    baseline = await _rows(
        context,
        "athlete_movement_baselines",
        filters={
            "exercise_id": f"eq.{session.get('exercise_id')}",
            "sensor_placement": f"eq.{session.get('sensor_placement')}",
            "status": "eq.AVAILABLE",
        },
        limit=1,
    ) if session.get("sensor_placement") else []
    quality = quality_rows[0] if quality_rows else {}
    fatigue = fatigue_rows[0] if fatigue_rows else {}
    return success(request, {
        "sessionId": session_id,
        "exerciseId": session.get("exercise_id"),
        "source": session.get("source"),
        "movementQuality": quality.get("movement_quality", session.get("movement_quality")),
        "consistency": quality.get("consistency"),
        "sensorQuality": quality.get("sensor_quality_status"),
        "fatigueSignal": fatigue.get("fatigue_state", session.get("fatigue_signal")),
        "fatigueTrend": fatigue.get("trend", "INSUFFICIENT_DATA"),
        "baselineStatus": quality.get("baseline_comparison", "PERSONAL_BASELINE_NOT_AVAILABLE"),
        "baselineAvailable": bool(baseline),
        "repetitions": repetitions,
        "anomalies": anomalies,
        "exerciseRecognition": {
            "status": quality.get("exercise_recognition_status", "MODEL_UNAVAILABLE"),
            "exercise": quality.get("recognized_exercise"),
            "modelVersion": quality.get("model_version"),
        },
        "modelAvailable": quality.get("model_version") is not None,
        "notice": "Movement intelligence describes sensor-derived signals; it is not a diagnosis or medical clearance.",
    })


@router.get("/movement-summary")
async def get_movement_summary(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict[str, Any]:
    sessions = await _rows(
        context, "rehab_sessions", filters={"status": "eq.COMPLETED"},
        order="ended_at.desc", limit=30,
    )
    qualities = [session.get("movement_quality") for session in sessions if session.get("movement_quality")]
    progress = classify_progress(qualities[::-1])
    return success(request, {
        "sessions": sessions,
        "sessionCount": len(sessions),
        "progress": progress,
        "latestQuality": qualities[0] if qualities else "INSUFFICIENT_DATA",
        "latestFatigueSignal": sessions[0].get("fatigue_signal") if sessions else "INSUFFICIENT_DATA",
        "notice": "Movement intelligence describes sensor-derived signals; it is not a diagnosis or medical clearance.",
    })
