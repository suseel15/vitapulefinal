from datetime import UTC, date, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.api.v1.health import AthleteContext, athlete_context
from app.core.config import Settings, get_settings
from app.core.responses import success
from app.ml.analysis import classify_progress
from app.repositories.health_repository import HealthRepository
from app.repositories.supabase import SupabaseRepository
from app.schemas.rehab import (
    FatigueSignal,
    FunctionalTestResultCreate,
    MovementQuality,
    MovementSummaryCreate,
    ReadinessEvaluate,
    ReadinessStatus,
    RehabSessionCreate,
    RehabSessionTransition,
    ReturnToSportEvaluate,
    SessionSource,
    SessionStatus,
)

router = APIRouter(prefix="/rehab", tags=["rehab"])


def _repository(context: AthleteContext) -> HealthRepository:
    athlete_id, _, client = context
    return HealthRepository(client, athlete_id)


def _client(context: AthleteContext) -> SupabaseRepository:
    return context[2]


async def _rows(
    context: AthleteContext,
    table: str,
    *,
    select: str = "*",
    order: str = "created_at.desc",
    limit: int = 100,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    return await _repository(context).list_rows(
        table,
        select=select,
        order=order,
        limit=limit,
        filters=filters,
    )


def _not_found(resource: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"The requested {resource} was not found.")


def _program_requirement_ids(value: Any, label: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise HTTPException(status_code=502, detail=f"The active program has invalid {label} identifiers.")
    try:
        return list(dict.fromkeys(str(UUID(item)) for item in value))
    except ValueError as error:
        raise HTTPException(status_code=502, detail=f"The active program has invalid {label} identifiers.") from error


async def _owned_session(context: AthleteContext, session_id: UUID) -> dict[str, Any]:
    records = await _rows(context, "rehab_sessions", filters={"id": f"eq.{session_id}"}, limit=1)
    if not records:
        raise _not_found("rehabilitation session")
    return records[0]


@router.get("/dashboard")
async def rehab_dashboard(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    programs = await _rows(
        context,
        "rehab_programs",
        order="updated_at.desc",
        filters={"status": "eq.ACTIVE"},
        limit=1,
    )
    recent_sessions = await _rows(
        context,
        "rehab_sessions",
        select="*,exercise:rehab_exercises(name)",
        order="started_at.desc.nullslast",
        limit=5,
    )
    functional_results = await _rows(context, "functional_test_results", limit=5)
    latest_readiness = await _rows(context, "readiness_assessments", limit=1)
    program = programs[0] if programs else None
    program_exercises = []
    completed_today = 0
    if program:
        program_exercises = await _client(context).rest(
            "GET",
            "rehab_program_exercises",
            params={
                "program_id": f"eq.{program['id']}",
                "athlete_id": f"eq.{context[0]}",
                "select": "*,exercise:rehab_exercises(*)",
                "order": "order_index.asc",
                "limit": "100",
            },
        )
        today_sessions = await _rows(
            context,
            "rehab_sessions",
            filters={"started_at": f"gte.{date.today().isoformat()}T00:00:00+00:00"},
            order="started_at.asc",
            limit=100,
        )
        statuses_by_exercise = {
            item["exercise_id"]: item["status"]
            for item in today_sessions
            if item.get("exercise_id")
        }
        for assignment in program_exercises:
            exercise_id = assignment.get("exercise_id")
            assignment["status"] = statuses_by_exercise.get(exercise_id, "NOT_STARTED")
        completed_today = len({
            item.get("exercise_id")
            for item in today_sessions
            if item.get("status") == SessionStatus.COMPLETED.value
        })
    return success(
        request,
        {
            "current_program": program,
            "current_stage": (
                {"name": program.get("stage"), "order": program.get("stage_order")}
                if program and program.get("stage")
                else None
            ),
            "today": {
                "exercises": program_exercises,
                "completed": completed_today,
                "remaining": max(0, len(program_exercises) - completed_today),
            },
            "readiness": latest_readiness[0] if latest_readiness else None,
            "movement_quality": recent_sessions[0].get("movement_quality") if recent_sessions else None,
            "recovery": {"status": "UNAVAILABLE", "sleep": None, "source": None},
            "progress": {
                "sessions_completed": sum(item.get("status") == SessionStatus.COMPLETED.value for item in recent_sessions),
                "functional_tests_completed": len(functional_results),
            },
            "recent_sessions": recent_sessions,
            "program_assigned": program is not None,
        },
    )


@router.get("/today")
async def get_today(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    dashboard = await rehab_dashboard(request, context)
    return success(request, dashboard["data"]["today"] | {
        "program": dashboard["data"]["current_program"],
        "stage": dashboard["data"]["current_stage"],
    })


@router.get("/program")
async def get_program(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    programs = await _rows(context, "rehab_programs", order="updated_at.desc", limit=100)
    if not programs:
        return success(request, {"program": None, "programs": []})
    program = next((item for item in programs if item.get("status") == "ACTIVE"), programs[0])
    exercises = await _client(context).rest(
        "GET",
        "rehab_program_exercises",
        params={
            "program_id": f"eq.{program['id']}",
            "athlete_id": f"eq.{context[0]}",
            "select": "*,exercise:rehab_exercises(*)",
            "order": "order_index.asc",
            "limit": "100",
        },
    )
    return success(request, {"program": program, "exercises": exercises, "programs": programs})


@router.get("/program/{program_id}")
async def get_program_by_id(
    request: Request,
    program_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    programs = await _rows(context, "rehab_programs", filters={"id": f"eq.{program_id}"}, limit=1)
    if not programs:
        raise _not_found("rehabilitation program")
    exercises = await _client(context).rest(
        "GET",
        "rehab_program_exercises",
        params={
            "program_id": f"eq.{program_id}",
            "athlete_id": f"eq.{context[0]}",
            "select": "*,exercise:rehab_exercises(*)",
            "order": "order_index.asc",
        },
    )
    return success(request, {"program": programs[0], "exercises": exercises})


@router.get("/exercises")
async def list_exercises(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
    category: str | None = None,
    search: str | None = None,
) -> dict:
    params = {"select": "*", "active": "eq.true", "order": "name.asc", "limit": "200"}
    if category:
        params["category"] = f"eq.{category}"
    if search:
        params["name"] = f"ilike.*{search.strip()}*"
    exercises = await _client(context).rest("GET", "rehab_exercises", params=params)
    return success(request, {"exercises": exercises})


@router.get("/exercises/{exercise_id}")
async def get_exercise(
    request: Request,
    exercise_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    records = await _client(context).rest(
        "GET",
        "rehab_exercises",
        params={"id": f"eq.{exercise_id}", "active": "eq.true", "select": "*", "limit": "1"},
    )
    if not records:
        raise _not_found("exercise")
    history = await _rows(
        context,
        "rehab_sessions",
        filters={"exercise_id": f"eq.{exercise_id}", "status": "eq.COMPLETED"},
        order="ended_at.desc",
        limit=5,
    )
    return success(request, {"exercise": records[0], "previous_performance": history})


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    request: Request,
    body: RehabSessionCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    if body.client_session_id is not None:
        existing = await _rows(
            context,
            "rehab_sessions",
            filters={"client_session_id": f"eq.{body.client_session_id}"},
            limit=1,
        )
        if existing:
            session = existing[0]
            if (
                session.get("exercise_id") != str(body.exercise_id)
                or session.get("source") != body.source.value
                or session.get("device_id") != (str(body.device_id) if body.device_id else None)
            ):
                raise HTTPException(status_code=409, detail="The client session identifier is already in use.")
            return success(request, {"session": session})
    if body.source == SessionSource.LIVE_SENSOR:
        devices = await _rows(
            context,
            "movement_devices",
            filters={"id": f"eq.{body.device_id}", "is_active": "eq.true"},
            limit=1,
        )
        if not devices:
            raise _not_found("registered movement device")
    exercises = await _client(context).rest(
        "GET",
        "rehab_exercises",
        params={"id": f"eq.{body.exercise_id}", "active": "eq.true", "select": "id", "limit": "1"},
    )
    if not exercises:
        raise _not_found("exercise")
    if body.program_id:
        program_exercises = await _client(context).rest(
            "GET",
            "rehab_program_exercises",
            params={
                "program_id": f"eq.{body.program_id}",
                "athlete_id": f"eq.{context[0]}",
                "exercise_id": f"eq.{body.exercise_id}",
                "select": "program_id",
                "limit": "1",
            },
        )
        owned_program = await _rows(context, "rehab_programs", filters={"id": f"eq.{body.program_id}"}, limit=1)
        if not owned_program or not program_exercises:
            raise _not_found("assigned program exercise")
    now = datetime.now(UTC).isoformat()
    session = await _repository(context).insert(
        "rehab_sessions",
        {
            **body.model_dump(mode="json"),
            "status": SessionStatus.PLANNED.value,
            "started_at": None,
            "ended_at": None,
            "sample_count": 0,
            "completed_repetitions": 0,
            "created_at": now,
            "updated_at": now,
            "source": body.source.value,
        },
    )
    return success(request, {"session": session})


@router.get("/sessions")
async def list_sessions(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
    limit: int = 100,
) -> dict:
    sessions = await _rows(
        context,
        "rehab_sessions",
        select="*,exercise:rehab_exercises(name)",
        order="started_at.desc.nullslast,created_at.desc",
        limit=max(1, min(limit, 200)),
    )
    return success(request, {"sessions": sessions})


@router.get("/sessions/{session_id}")
async def get_session(
    request: Request,
    session_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    session = await _owned_session(context, session_id)
    repetitions = await _rows(
        context,
        "rehab_repetitions",
        filters={"session_id": f"eq.{session_id}"},
        order="rep_number.asc",
    )
    return success(request, {"session": session, "repetitions": repetitions})


@router.patch("/sessions/{session_id}")
async def transition_session(
    request: Request,
    session_id: UUID,
    body: RehabSessionTransition,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    current = await _owned_session(context, session_id)
    allowed = {
        "PLANNED": {"CALIBRATING", "ACTIVE", "CANCELLED"},
        "CALIBRATING": {"ACTIVE", "CANCELLED", "ERROR"},
        "ACTIVE": {"PAUSED", "COMPLETED", "CANCELLED", "ERROR"},
        "PAUSED": {"ACTIVE", "COMPLETED", "CANCELLED", "ERROR"},
    }
    if body.status.value not in allowed.get(current["status"], set()):
        raise HTTPException(status_code=409, detail=f"Cannot move a {current['status'].lower()} session to {body.status.value.lower()}.")
    updates: dict[str, Any] = {"status": body.status.value, "updated_at": datetime.now(UTC).isoformat()}
    if body.status == SessionStatus.ACTIVE and not current.get("started_at"):
        updates["started_at"] = datetime.now(UTC).isoformat()
    if body.status in {SessionStatus.COMPLETED, SessionStatus.CANCELLED, SessionStatus.ERROR}:
        updates["ended_at"] = datetime.now(UTC).isoformat()
    session = await _repository(context).patch("rehab_sessions", session_id, updates)
    if session is None:
        raise _not_found("rehabilitation session")
    return success(request, {"session": session})


@router.post("/sessions/{session_id}/movement-summary")
async def save_movement_summary(
    request: Request,
    session_id: UUID,
    body: MovementSummaryCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    session = await _owned_session(context, session_id)
    completed_summary_retry = False
    if session["status"] == SessionStatus.COMPLETED.value:
        completed_summary_retry = bool(await _rows(
            context,
            "movement_quality_results",
            filters={"session_id": f"eq.{session_id}"},
            limit=1,
        ))
    if session["status"] not in {SessionStatus.ACTIVE.value, SessionStatus.PAUSED.value} and not completed_summary_retry:
        raise HTTPException(status_code=409, detail="Movement results can only be saved for an active session.")
    if body.source.value != session["source"]:
        raise HTTPException(status_code=422, detail="Movement source must match the session source.")
    if body.source == SessionSource.LIVE_SENSOR:
        if str(body.device_id) != session.get("device_id"):
            raise HTTPException(status_code=422, detail="Movement summary device must match the session device.")
        devices = await _rows(
            context,
            "movement_devices",
            filters={"id": f"eq.{body.device_id}", "is_active": "eq.true"},
            limit=1,
        )
        if not devices:
            raise _not_found("registered movement device")
    if len(body.repetitions) > body.completed_repetitions:
        raise HTTPException(status_code=422, detail="Recorded repetitions cannot exceed the completed repetition count.")
    athlete_id = str(context[0])
    client = _client(context)
    if body.repetitions:
        await client.rest(
            "POST",
            "rehab_repetitions",
            payload=[
                {
                    **rep.model_dump(mode="json"),
                    "athlete_id": athlete_id,
                    "session_id": str(session_id),
                    "source": body.source.value,
                }
                for rep in body.repetitions
            ],
            params={"on_conflict": "session_id,rep_number"},
            prefer="resolution=merge-duplicates,return=minimal",
        )
    if body.metrics:
        await client.rest(
            "POST",
            "movement_metrics",
            payload=[
                {
                    **metric.model_dump(),
                    "athlete_id": athlete_id,
                    "session_id": str(session_id),
                    "source": body.source.value,
                }
                for metric in body.metrics
            ],
            params={"on_conflict": "session_id,metric_name"},
            prefer="resolution=merge-duplicates,return=minimal",
        )
    intelligence = body.movement_intelligence
    if intelligence is not None:
        if intelligence.prediction_source == "MODEL_INFERRED" and intelligence.model_version is None:
            raise HTTPException(status_code=422, detail="Model-derived results require a model version.")
        if intelligence.events:
            await client.rest(
                "POST",
                "movement_events",
                payload=[
                    {
                        "athlete_id": athlete_id,
                        "session_id": str(session_id),
                        "timestamp": datetime.fromtimestamp(event.timestamp / 1000, UTC).isoformat(),
                        "event_type": event.event_type,
                        "severity": event.severity,
                        "description": event.description,
                        "source": event.source,
                    }
                    for event in intelligence.events
                ],
                params={"on_conflict": "session_id,event_type,timestamp"},
                prefer="resolution=merge-duplicates,return=minimal",
            )
        if intelligence.anomalies:
            await client.rest(
                "POST",
                "movement_anomaly_results",
                payload=[
                    {
                        "athlete_id": athlete_id,
                        "session_id": str(session_id),
                        "event_timestamp": datetime.fromtimestamp(item.event_timestamp / 1000, UTC).isoformat(),
                        "anomaly_type": item.anomaly_type,
                        "severity": item.severity,
                        "baseline_deviation": item.baseline_deviation,
                        "model_name": item.model_name,
                        "model_version": item.model_version,
                        "requires_review": item.requires_review,
                        "source": "MODEL_INFERRED" if item.model_version else "CALCULATED",
                    }
                    for item in intelligence.anomalies
                ],
                params={"on_conflict": "session_id,event_timestamp,anomaly_type"},
                prefer="resolution=merge-duplicates,return=minimal",
            )
        if (
            intelligence.exercise_recognition_status == "RECOGNIZED"
            and intelligence.prediction_source == "MODEL_INFERRED"
            and intelligence.model_name
            and intelligence.model_version
            and intelligence.feature_schema_version
            and intelligence.prediction_timestamp is not None
            and intelligence.recognized_exercise
        ):
            await client.rest(
                "POST",
                "movement_predictions",
                payload={
                    "athlete_id": athlete_id,
                    "session_id": str(session_id),
                    "exercise_id": session["exercise_id"],
                    "prediction_type": "EXERCISE_CLASS",
                    "prediction": intelligence.recognized_exercise,
                    "model_name": intelligence.model_name,
                    "model_version": intelligence.model_version,
                    "feature_schema_version": intelligence.feature_schema_version,
                    "timestamp": datetime.fromtimestamp(intelligence.prediction_timestamp / 1000, UTC).isoformat(),
                    "source": "MODEL_INFERRED",
                },
                params={"on_conflict": "session_id,timestamp,prediction_type"},
                prefer="resolution=merge-duplicates,return=minimal",
            )
        fatigue_values = [rep.duration_ms for rep in body.repetitions]
        fatigue_trend = _fatigue_trend(fatigue_values)
        await client.rest(
            "POST",
            "movement_fatigue_results",
            payload={
                "athlete_id": athlete_id,
                "session_id": str(session_id),
                "fatigue_state": body.fatigue_signal.value,
                "trend": fatigue_trend,
                "supporting_metrics": {
                    "repetition_count": len(fatigue_values),
                    "calculated_from_rep_durations": len(fatigue_values) >= 6,
                },
                "calculation_version": intelligence.calculation_version,
                "source": "CALCULATED" if body.source == SessionSource.MANUAL else body.source.value,
            },
            params={"on_conflict": "session_id"},
            prefer="resolution=merge-duplicates,return=minimal",
        )
    await client.rest(
        "POST",
        "movement_quality_results",
        payload={
            "athlete_id": athlete_id,
            "session_id": str(session_id),
            "movement_quality": body.movement_quality.value,
            "stability": body.stability.value,
            "smoothness": body.smoothness.value,
            "fatigue_signal": body.fatigue_signal.value,
            "abnormal_events": body.abnormal_events,
            "source": body.source.value,
            "consistency": intelligence.consistency if intelligence else None,
            "sensor_quality_status": intelligence.sensor_quality_status.value if intelligence else None,
            "baseline_comparison": intelligence.baseline_status.value if intelligence else None,
            "exercise_recognition_status": intelligence.exercise_recognition_status if intelligence else None,
            "recognized_exercise": intelligence.recognized_exercise if intelligence else None,
            "prediction_source": intelligence.prediction_source if intelligence else None,
            "model_name": intelligence.model_name if intelligence else None,
            "model_version": intelligence.model_version if intelligence else None,
            "feature_schema_version": intelligence.feature_schema_version if intelligence else None,
            "processing_version": intelligence.calculation_version if intelligence else None,
        },
        params={"on_conflict": "session_id"},
        prefer="resolution=merge-duplicates,return=minimal",
    )
    updated = await _repository(context).patch(
        "rehab_sessions",
        session_id,
        {
            "source": body.source.value,
            "sensor_placement": body.sensor_placement.value if body.sensor_placement else None,
            "sample_count": body.sample_count,
            "target_repetitions": body.target_repetitions,
            "completed_repetitions": body.completed_repetitions,
            "session_duration_seconds": body.session_duration_seconds,
            "successful_requests": body.successful_requests,
            "failed_requests": body.failed_requests,
            "invalid_samples": body.invalid_samples,
            "measured_rate_hz": body.measured_rate_hz,
            "average_latency_ms": body.average_latency_ms,
            "completion_rate": (
                body.completed_repetitions / body.target_repetitions
                if body.target_repetitions
                else None
            ),
            "movement_quality": body.movement_quality.value,
            "stability": body.stability.value,
            "smoothness": body.smoothness.value,
            "fatigue_signal": body.fatigue_signal.value,
            "safety_events": body.abnormal_events,
            "status": SessionStatus.COMPLETED.value,
            "ended_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )
    if updated is None:
        raise _not_found("rehabilitation session")
    if body.source == SessionSource.LIVE_SENSOR and body.device_id is not None:
        await _repository(context).patch(
            "movement_devices",
            body.device_id,
            {"last_seen_at": datetime.now(UTC).isoformat()},
        )
    if body.source == SessionSource.LIVE_SENSOR and intelligence is not None:
        baseline_status = await _update_movement_baseline(context, updated, body, settings)
        quality_rows = await _rows(
            context,
            "movement_quality_results",
            filters={"session_id": f"eq.{session_id}"},
            limit=1,
        )
        if quality_rows:
            await client.rest(
                "PATCH",
                "movement_quality_results",
                params={"id": f"eq.{quality_rows[0]['id']}", "athlete_id": f"eq.{athlete_id}"},
                payload={"baseline_comparison": baseline_status},
                prefer="return=minimal",
            )
    return success(request, {"session": updated})


async def _update_movement_baseline(
    context: AthleteContext,
    session: dict[str, Any],
    body: MovementSummaryCreate,
    settings: Settings,
) -> str:
    intelligence = body.movement_intelligence
    placement = session.get("sensor_placement")
    exercise_id = session.get("exercise_id")
    if (
        intelligence is None
        or placement is None
        or not exercise_id
        or intelligence.sensor_quality_status.value not in {"EXCELLENT", "GOOD"}
        or body.sample_count < 20
        or body.movement_quality == MovementQuality.INSUFFICIENT_DATA
        or len(body.repetitions) < 3
    ):
        return "PERSONAL_BASELINE_NOT_AVAILABLE"

    filters = {
        "exercise_id": f"eq.{exercise_id}",
        "sensor_placement": f"eq.{placement}",
        "source": "eq.LIVE_SENSOR",
        "status": "eq.COMPLETED",
        "sample_count": "gte.20",
    }
    eligible_sessions = await _rows(context, "rehab_sessions", filters=filters, limit=200)
    if not eligible_sessions:
        return "PERSONAL_BASELINE_NOT_AVAILABLE"
    session_ids = [str(item["id"]) for item in eligible_sessions]
    quality_rows = await _rows(
        context,
        "movement_quality_results",
        filters={"session_id": f"in.({','.join(session_ids)})"},
        limit=500,
    )
    good_quality_sessions = {
        row["session_id"]
        for row in quality_rows
        if row.get("sensor_quality_status") in {"EXCELLENT", "GOOD"}
        and row.get("movement_quality") != MovementQuality.INSUFFICIENT_DATA.value
    }
    eligible_ids = [session_id for session_id in session_ids if session_id in good_quality_sessions]
    if not eligible_ids:
        return "PERSONAL_BASELINE_NOT_AVAILABLE"
    repetitions = await _rows(
        context,
        "rehab_repetitions",
        filters={"session_id": f"in.({','.join(eligible_ids)})"},
        order="created_at.asc",
        limit=5000,
    )
    repetitions = [item for item in repetitions if item.get("duration_ms", 0) > 0]
    distinct_sessions = {item["session_id"] for item in repetitions}
    if (
        len(distinct_sessions) < settings.baseline_min_sessions
        or len(repetitions) < settings.baseline_min_repetitions
    ):
        return "PERSONAL_BASELINE_NOT_AVAILABLE"

    baseline_rows = await _rows(
        context,
        "athlete_movement_baselines",
        filters={
            "exercise_id": f"eq.{exercise_id}",
            "sensor_placement": f"eq.{placement}",
        },
        limit=1,
    )
    previous = baseline_rows[0] if baseline_rows else None
    durations = [float(item["duration_ms"]) for item in repetitions]
    average = sum(durations) / len(durations)
    deviation = (sum((value - average) ** 2 for value in durations) / len(durations)) ** 0.5
    means = {
        "mean_rep_duration_ms": average,
        "valid_repetition_count": len(repetitions),
    }
    deviations = {"rep_duration_ms": deviation}
    comparison = "PERSONAL_BASELINE_NOT_AVAILABLE"
    if previous:
        old_means = previous.get("mean_features") or {}
        old_std = previous.get("std_features") or {}
        old_average = old_means.get("mean_rep_duration_ms")
        old_deviation = old_std.get("rep_duration_ms")
        if isinstance(old_average, (int, float)) and isinstance(old_deviation, (int, float)):
            scale = max(float(old_deviation), float(old_average) * 0.1, 1.0)
            difference = (average - float(old_average)) / scale
            if abs(difference) >= 2:
                comparison = "DEVIATION_DETECTED"
            elif average <= float(old_average) * 0.9:
                comparison = "IMPROVED"
            else:
                comparison = "STABLE"

    baseline_record = {
        "exercise_id": exercise_id,
        "sensor_placement": placement,
        "baseline_version": (int(previous.get("baseline_version", 0)) + 1) if previous else 1,
        "sample_count": sum(int(item.get("sample_count", 0)) for item in eligible_sessions),
        "session_count": len(distinct_sessions),
        "repetition_count": len(repetitions),
        "mean_features": means,
        "std_features": deviations,
        "status": "AVAILABLE",
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if previous and all(
        previous.get(field) == baseline_record[field]
        for field in ("sample_count", "session_count", "repetition_count", "mean_features", "std_features", "status")
    ):
        return comparison
    await _repository(context).upsert(
        "athlete_movement_baselines",
        baseline_record,
        conflict="athlete_id,exercise_id,sensor_placement",
    )
    return comparison


@router.post("/sessions/{session_id}/complete")
async def complete_session(
    request: Request,
    session_id: UUID,
    body: MovementSummaryCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    return await save_movement_summary(request, session_id, body, context)


@router.post("/sessions/{session_id}/cancel")
async def cancel_session(
    request: Request,
    session_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    return await transition_session(
        request,
        session_id,
        RehabSessionTransition(status=SessionStatus.CANCELLED),
        context,
    )


@router.get("/sessions/{session_id}/movement")
async def get_session_movement(
    request: Request,
    session_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    await _owned_session(context, session_id)
    repetitions = await _rows(context, "rehab_repetitions", filters={"session_id": f"eq.{session_id}"}, order="rep_number.asc")
    metrics = await _rows(context, "movement_metrics", filters={"session_id": f"eq.{session_id}"})
    quality = await _rows(context, "movement_quality_results", filters={"session_id": f"eq.{session_id}"}, limit=1)
    events = await _rows(context, "movement_events", filters={"session_id": f"eq.{session_id}"}, order="timestamp.asc")
    predictions = await _rows(context, "movement_predictions", filters={"session_id": f"eq.{session_id}"}, order="timestamp.asc")
    anomalies = await _rows(context, "movement_anomaly_results", filters={"session_id": f"eq.{session_id}"}, order="event_timestamp.asc")
    fatigue = await _rows(context, "movement_fatigue_results", filters={"session_id": f"eq.{session_id}"}, limit=1)
    return success(request, {
        "repetitions": repetitions,
        "metrics": metrics,
        "quality": quality[0] if quality else None,
        "events": events,
        "predictions": predictions,
        "anomalies": anomalies,
        "fatigue": fatigue[0] if fatigue else None,
    })


@router.get("/movement/summary")
async def movement_summary(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    sessions = await _rows(context, "rehab_sessions", filters={"status": "eq.COMPLETED"}, order="ended_at.desc", limit=30)
    qualities = [record["movement_quality"] for record in sessions if record.get("movement_quality")]
    anomalies = await _rows(context, "movement_anomaly_results", order="event_timestamp.desc", limit=20)
    baselines = await _rows(context, "athlete_movement_baselines", order="updated_at.desc", limit=20)
    return success(request, {
        "sessions": sessions,
        "session_count": len(sessions),
        "movement_quality": qualities[0] if qualities else MovementQuality.INSUFFICIENT_DATA.value,
        "trend": classify_progress(qualities[::-1]),
        "fatigue_signal": sessions[0].get("fatigue_signal") if sessions else FatigueSignal.INSUFFICIENT_DATA.value,
        "anomalies": anomalies,
        "personal_baselines": baselines,
        "notice": "Movement signals are descriptive and are not a diagnosis or full-body biomechanics assessment.",
    })


@router.get("/movement/trends")
async def movement_trends(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    sessions = await _rows(context, "rehab_sessions", filters={"status": "eq.COMPLETED"}, order="ended_at.asc", limit=100)
    if len(sessions) < 3:
        return success(request, {
            "available": False,
            "reason": "Not enough sessions for a meaningful trend.",
            "sessions": [],
            "movement_quality_trend": "INSUFFICIENT_DATA",
        })
    quality_trend = classify_progress([item["movement_quality"] for item in sessions if item.get("movement_quality")])
    return success(request, {
        "available": True,
        "movement_quality_trend": quality_trend,
        "sessions": [
            {"ended_at": item.get("ended_at"), "movement_quality": item.get("movement_quality"),
             "completed_repetitions": item.get("completed_repetitions"), "session_duration_seconds": item.get("session_duration_seconds")}
            for item in sessions
        ],
    })


def _fatigue_trend(durations_ms: list[int]) -> str:
    if len(durations_ms) < 6 or any(duration <= 0 for duration in durations_ms):
        return "INSUFFICIENT_DATA"
    midpoint = len(durations_ms) // 2
    first = sum(durations_ms[:midpoint]) / midpoint
    last_values = durations_ms[midpoint:]
    last = sum(last_values) / len(last_values)
    relative_change = (last - first) / first
    if relative_change >= 0.15:
        return "WORSENING"
    if relative_change <= -0.15:
        return "IMPROVING"
    return "STABLE"


@router.get("/progress")
async def get_progress(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    programs = await _rows(context, "rehab_programs", filters={"status": "eq.ACTIVE"}, limit=1)
    sessions = await _rows(context, "rehab_sessions", filters={"status": "eq.COMPLETED"}, limit=200)
    completed_tests = await _rows(context, "functional_test_results", limit=100)
    baselines = await _rows(context, "athlete_movement_baselines", order="updated_at.desc", limit=20)
    anomalies = await _rows(context, "movement_anomaly_results", order="event_timestamp.desc", limit=20)
    assigned_count = completed_count = 0
    program = programs[0] if programs else None
    if program:
        assigned = await _client(context).rest(
            "GET", "rehab_program_exercises",
            params={
                "program_id": f"eq.{program['id']}",
                "athlete_id": f"eq.{context[0]}",
                "select": "exercise_id,required",
                "limit": "200",
            },
        )
        assigned_count = len(assigned)
        completed_ids = {item.get("exercise_id") for item in sessions}
        completed_count = sum(item.get("exercise_id") in completed_ids for item in assigned)
    return success(request, {
        "program": program,
        "sessions_completed": len(sessions),
        "exercises_completed": completed_count,
        "assigned_exercises": assigned_count,
        "functional_tests_completed": len(completed_tests),
        "movement_trend": classify_progress([
            item["movement_quality"] for item in reversed(sessions) if item.get("movement_quality")
        ]),
        "personal_baselines": baselines,
        "anomaly_history": anomalies,
        "fatigue_trend": (
            (await _rows(context, "movement_fatigue_results", order="created_at.asc", limit=200))
        ),
        "return_to_sport_status": "NOT_STARTED" if not program else "IN_PROGRESS",
    })


@router.get("/functional-tests")
async def list_functional_tests(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    tests = await _client(context).rest(
        "GET", "functional_tests", params={"select": "*", "active": "eq.true", "order": "name.asc"}
    )
    tests = [test for test in tests if test.get("name") in {"Balance Test", "Single-Leg Stability"}]
    history = await _rows(
        context,
        "functional_test_results",
        select="*,functional_test:functional_tests(name)",
        order="created_at.desc",
        limit=30,
    )
    return success(request, {"tests": tests, "history": history})


@router.post("/functional-tests/{test_id}/results", status_code=status.HTTP_201_CREATED)
async def create_functional_test_result(
    request: Request,
    test_id: UUID,
    body: FunctionalTestResultCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    tests = await _client(context).rest(
        "GET", "functional_tests", params={"id": f"eq.{test_id}", "active": "eq.true", "select": "id,name", "limit": "1"}
    )
    if not tests:
        raise _not_found("functional test")
    if tests[0]["name"] not in {"Balance Test", "Single-Leg Stability"}:
        raise HTTPException(status_code=422, detail="This functional test has no validated measurement method yet.")
    result = await _repository(context).insert(
        "functional_test_results",
        {"functional_test_id": str(test_id), **body.model_dump(mode="json"), "result": "RECORDED"},
    )
    return success(request, {"result": result})


@router.get("/functional-tests/history")
async def functional_test_history(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    return success(request, {"results": await _rows(context, "functional_test_results", order="created_at.desc", limit=100)})


def _readiness(
    sessions: list[dict[str, Any]],
    latest_quality: str | None,
    self_report: str | None,
    soreness: str | None,
    safety_events: list[str],
) -> tuple[ReadinessStatus, str, list[dict[str, str]]]:
    factors: list[dict[str, str]] = []
    if self_report:
        factors.append({"factor": "athlete_report", "value": self_report})
    if soreness:
        factors.append({"factor": "soreness", "value": soreness})
    if latest_quality:
        factors.append({"factor": "last_recorded_movement_quality", "value": latest_quality})
    if sessions:
        factors.append({"factor": "recent_completed_sessions", "value": str(len(sessions))})
    if safety_events:
        factors.append({"factor": "unresolved_movement_warnings", "value": str(len(safety_events))})
        return ReadinessStatus.REVIEW_REQUIRED, "Review the recorded movement warning before continuing with rehabilitation.", factors
    if self_report == "PAIN_OR_CONCERN":
        return ReadinessStatus.REVIEW_REQUIRED, "Pause and discuss the concern with your clinician before continuing.", factors
    if soreness == "SEVERE":
        return ReadinessStatus.REST_RECOMMENDED, "Consider resting and seek appropriate professional guidance if needed.", factors
    if not sessions and not self_report and not soreness:
        return ReadinessStatus.INSUFFICIENT_DATA, "There is not enough information to estimate today's rehab readiness.", factors
    if self_report in {"FATIGUED", "SORE"} or soreness == "MODERATE" or latest_quality == "NEEDS_ATTENTION":
        return ReadinessStatus.READY_WITH_CAUTION, "If you continue, reduce intensity and monitor how you feel.", factors
    return ReadinessStatus.READY, "Use your assigned program and stop if you experience pain or a concerning change.", factors


async def _evaluate_readiness(context: AthleteContext, body: ReadinessEvaluate | None = None) -> dict[str, Any]:
    all_sessions = await _rows(context, "rehab_sessions", filters={"status": "eq.COMPLETED"}, order="ended_at.desc", limit=200)
    sessions = all_sessions[:3]
    safety_events = [
        event
        for session in all_sessions
        for event in (session.get("safety_events") or [])
    ]
    assessment, recommendation, factors = _readiness(
        sessions,
        sessions[0].get("movement_quality") if sessions else None,
        body.self_reported_status if body else None,
        body.soreness if body else None,
        safety_events,
    )
    record = await _repository(context).insert(
        "readiness_assessments",
        {
            "status": assessment.value,
            "factors": factors,
            "recommendation": recommendation,
            "source": "RULE_BASED",
        },
    )
    return record


@router.get("/readiness/current")
async def current_readiness(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    assessments = await _rows(context, "readiness_assessments", limit=1)
    return success(request, {"assessment": assessments[0] if assessments else None})


@router.post("/readiness/evaluate")
async def evaluate_readiness(
    request: Request,
    body: ReadinessEvaluate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    return success(request, {"assessment": await _evaluate_readiness(context, body)})


@router.get("/readiness/history")
async def readiness_history(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    return success(request, {"assessments": await _rows(context, "readiness_assessments", limit=100)})


@router.get("/return-to-sport")
async def get_return_to_sport(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    assessments = await _rows(context, "return_to_sport_assessments", limit=1)
    return success(request, {"assessment": assessments[0] if assessments else None, "medical_clearance": False})


@router.post("/return-to-sport/evaluate")
async def evaluate_return_to_sport(
    request: Request,
    body: ReturnToSportEvaluate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    programs = await _rows(context, "rehab_programs", filters={"status": "eq.ACTIVE"}, limit=1)
    sessions = await _rows(context, "rehab_sessions", filters={"status": "eq.COMPLETED"}, limit=200)
    results = await _rows(context, "functional_test_results", limit=100)
    program = programs[0] if programs else None
    config = (program or {}).get("return_to_sport_requirements") or {}
    minimum_sessions = config.get("minimum_completed_sessions", 0)
    if isinstance(minimum_sessions, bool) or not isinstance(minimum_sessions, int) or minimum_sessions < 0:
        raise HTTPException(status_code=502, detail="The active program has invalid return-to-sport session requirements.")
    required_exercise_ids = _program_requirement_ids(config.get("required_exercise_ids"), "required exercise")
    required_test_ids = _program_requirement_ids(config.get("required_functional_test_ids"), "functional test")
    require_functional_test = config.get("require_functional_test", True)
    require_athlete_report = config.get("require_athlete_report", False)
    if not isinstance(require_functional_test, bool) or not isinstance(require_athlete_report, bool):
        raise HTTPException(status_code=502, detail="The active program has invalid return-to-sport requirements.")
    required = []
    if program:
        required = await _client(context).rest(
            "GET",
            "rehab_program_exercises",
            params={
                "program_id": f"eq.{program['id']}",
                "athlete_id": f"eq.{context[0]}",
                "required": "eq.true",
                "select": "exercise_id",
                "limit": "200",
            },
        )
    if required_exercise_ids is not None:
        required = [{"exercise_id": item} for item in required_exercise_ids]
    completed_ids = {session.get("exercise_id") for session in sessions}
    done = [item for item in required if item.get("exercise_id") in completed_ids]
    outstanding = [item for item in required if item.get("exercise_id") not in completed_ids]
    if program:
        sessions = [item for item in sessions if item.get("program_id") == program["id"]]
        completed_ids = {session.get("exercise_id") for session in sessions}
        done = [item for item in required if item.get("exercise_id") in completed_ids]
        outstanding = [item for item in required if item.get("exercise_id") not in completed_ids]
    if required_test_ids is not None:
        required_test_set = set(required_test_ids)
        results = [item for item in results if item.get("functional_test_id") in required_test_set]
    completed_test_ids = {item.get("functional_test_id") for item in results}
    outstanding_tests = [
        {"type": "functional_test_result", "functional_test_id": item}
        for item in required_test_ids or []
        if item not in completed_test_ids
    ]
    athlete_status = body.athlete_reported_status
    unresolved_safety = any(bool(session.get("safety_events")) for session in sessions)
    if len(sessions) < minimum_sessions:
        outstanding.append({"type": "minimum_completed_sessions", "required": minimum_sessions, "completed": len(sessions)})
    if require_athlete_report and athlete_status is None:
        outstanding.append({"type": "athlete_report"})
    if require_functional_test:
        outstanding.extend(outstanding_tests)
    has_required_test = bool(results) if required_test_ids is None else not outstanding_tests
    status_name = (
        "NOT_STARTED" if not program
        else "REVIEW_REQUIRED" if athlete_status == "NOT_READY" or unresolved_safety
        else "READY_FOR_REVIEW" if not outstanding and (has_required_test or not require_functional_test) and athlete_status == "READY_FOR_REVIEW"
        else "PROGRESSION_RECOMMENDED" if not outstanding and (has_required_test or not require_functional_test)
        else "IN_PROGRESS"
    )
    record = await _repository(context).insert(
        "return_to_sport_assessments",
        {
            "program_id": str(program["id"]) if program else None,
            "stage": program.get("stage") if program else None,
            "status": status_name,
            "requirements": {
                "configured": config,
                "required_exercises": required,
                "functional_test_required": require_functional_test,
                "required_functional_test_ids": required_test_ids,
                "unresolved_safety_events": unresolved_safety,
            },
            "completed_requirements": {"exercises": done, "functional_tests": results},
            "outstanding_requirements": outstanding + (
                [{"type": "functional_test_result"}]
                if require_functional_test and required_test_ids is None and not results else []
            ),
            "clinician_review_status": "PENDING",
            "source": "RULE_BASED",
        },
    )
    return success(request, {"assessment": record, "medical_clearance": False})


@router.get("/history")
async def rehab_history(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    return success(request, {"sessions": await _rows(
        context,
        "rehab_sessions",
        select="*,exercise:rehab_exercises(name)",
        order="started_at.desc.nullslast,created_at.desc",
        limit=200,
    )})


@router.get("/reports")
async def rehab_reports(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    records = await _rows(context, "rehab_reports", order="created_at.desc", limit=100)
    return success(request, {
        "reports": records,
        "available_types": [
            "REHAB_SESSION", "MOVEMENT_ANALYSIS", "EXERCISE_PROGRESS", "FUNCTIONAL_TEST",
            "READINESS", "RETURN_TO_SPORT", "WEEKLY_REHAB", "MONTHLY_REHAB",
        ],
        "note": "Report data contracts are available; rendered PDF and generated narrative are not implemented.",
    })


@router.get("/recovery")
async def rehab_recovery(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    sessions = await _rows(context, "rehab_sessions", filters={"status": "eq.COMPLETED"}, order="ended_at.desc", limit=7)
    return success(request, {
        "recent_rehab_load": sum(int(item.get("session_duration_seconds") or 0) for item in sessions),
        "recent_session_count": len(sessions),
        "fatigue_signal": sessions[0].get("fatigue_signal") if sessions else FatigueSignal.INSUFFICIENT_DATA.value,
        "soreness": None,
        "sleep": {"status": "NOT_CONNECTED", "value": None},
        "recovery_notes": [],
        "recovery_data_available": False,
    })
