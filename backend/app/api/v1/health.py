import logging
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.responses import success
from app.core.security import bearer_scheme, require_roles
from app.repositories.biomarker_repository import BiomarkerRepository
from app.repositories.body_map_repository import BodyMapRepository
from app.repositories.health_repository import HealthRepository
from app.repositories.medical_report_repository import MedicalReportRepository
from app.repositories.supabase import SupabaseRepository
from app.schemas.anti_doping import AntiDopingStatus
from app.schemas.body_map import BodyRegionFindingCreate, BodyFindingState
from app.schemas.health import HealthReportCreate
from app.schemas.medical_report import MedicalReportResponse
from app.schemas.medication import MedicationCreate, MedicationUpdate
from app.schemas.nutrition import NutritionEntryCreate, NutritionProfileUpdate
from app.services.medical_report_service import upload_medical_report

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])

AthleteContext = tuple[UUID, Settings, SupabaseRepository]


async def athlete_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    profile: Annotated[dict[str, Any], Depends(require_roles("ATHLETE"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AthleteContext:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        athlete_id = UUID(str(profile["id"]))
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="An athlete profile is required.") from error
    return athlete_id, settings, SupabaseRepository(settings, credentials.credentials, service_role=True)


def _health_repo(context: AthleteContext) -> HealthRepository:
    athlete_id, _, client = context
    return HealthRepository(client, athlete_id)


def _medical_report_response(record: dict[str, Any]) -> dict[str, Any]:
    try:
        return MedicalReportResponse.model_validate(record).model_dump(mode="json")
    except ValidationError as error:
        logger.error("A medical report did not match its response contract.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The health data service returned an invalid report.",
        ) from error


async def _audit(
    client: SupabaseRepository,
    athlete_id: UUID,
    event_type: str,
    resource_type: str,
    resource_id: UUID | None = None,
) -> None:
    await client.rest(
        "POST",
        "health_audit_events",
        payload={
            "actor_id": str(athlete_id),
            "athlete_id": str(athlete_id),
            "event_type": event_type,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
        },
    )


@router.get("/overview")
async def health_overview(request: Request, context: Annotated[AthleteContext, Depends(athlete_context)]) -> dict:
    athlete_id, _, client = context
    reports = MedicalReportRepository(client, athlete_id)
    health = _health_repo(context)
    report_rows, measurements, findings, medications, doping_reviews, screenings = await _gather(
        reports.list(),
        BiomarkerRepository(client, athlete_id).list_measurements(),
        BodyMapRepository(client, athlete_id).findings(),
        health.list_rows("medications", filters={"status": "eq.ACTIVE"}),
        health.list_rows("anti_doping_reviews"),
        health.list_rows("skin_screenings"),
    )
    return success(
        request,
        {
            "latest_report": _medical_report_response(report_rows[0]) if report_rows else None,
            "tracked_biomarker_count": len({row.get("canonical_name") or row.get("biomarker_name") for row in measurements}),
            "recent_findings": findings[:5],
            "medication_count": len(medications),
            "anti_doping_review_status": (
                doping_reviews[0]["status"] if doping_reviews else AntiDopingStatus.INSUFFICIENT_INFORMATION.value
            ),
            "skin_screening_status": screenings[0]["result"] if screenings else "NOT_AVAILABLE",
            "health_intelligence_status": "NOT_CONFIGURED",
        },
    )


async def _gather(*coroutines: Any) -> list[Any]:
    import asyncio

    return list(await asyncio.gather(*coroutines))


@router.get("/medical-reports")
async def list_medical_reports(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    athlete_id, _, client = context
    records = await MedicalReportRepository(client, athlete_id).list()
    return success(request, {"reports": [_medical_report_response(record) for record in records]})


@router.post("/medical-reports", status_code=status.HTTP_202_ACCEPTED)
async def create_medical_report(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile,
    consent: Annotated[bool, Form()],
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    if not consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consent is required to process a medical report.",
        )
    athlete_id, settings, client = context
    content = await file.read(settings.max_upload_size_mb * 1024 * 1024 + 1)
    report = await upload_medical_report(
        athlete_id=athlete_id,
        content=content,
        filename=file.filename or "medical-report",
        mime_type=file.content_type or "",
        settings=settings,
        background_tasks=background_tasks,
    )
    report_id = UUID(report["id"])
    await _audit(client, athlete_id, "MEDICAL_REPORT_UPLOADED", "medical_report", report_id)
    return success(request, {"report": _medical_report_response(report)})


@router.get("/medical-reports/{report_id}")
async def get_medical_report(
    request: Request,
    report_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    athlete_id, _, client = context
    report = await MedicalReportRepository(client, athlete_id).get(report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The requested report was not found.")
    measurements = await BiomarkerRepository(client, athlete_id).list_measurements(report_id)
    return success(request, {"report": _medical_report_response(report), "biomarkers": measurements})


@router.post("/medical-reports/{report_id}/source")
async def create_report_source_link(
    request: Request,
    report_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    athlete_id, settings, client = context
    report = await MedicalReportRepository(client, athlete_id).get(report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The requested report was not found.")
    await _audit(client, athlete_id, "MEDICAL_REPORT_SOURCE_ACCESSED", "medical_report", report_id)
    signed_url = await client.signed_url(
        report["storage_bucket"],
        report["storage_path"],
        settings.signed_url_expiry_seconds,
    )
    return success(
        request,
        {
            "url": signed_url,
            "expires_in_seconds": settings.signed_url_expiry_seconds,
            "expires_at": (datetime.now(UTC) + timedelta(seconds=settings.signed_url_expiry_seconds)).isoformat(),
        },
    )


@router.delete("/medical-reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medical_report(
    report_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> None:
    athlete_id, _, client = context
    repository = MedicalReportRepository(client, athlete_id)
    report = await repository.get(report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The requested report was not found.")
    if report["processing_status"] not in {"COMPLETED", "FAILED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Wait for report processing to finish before deleting it.",
        )
    original_content = await client.download_object(report["storage_bucket"], report["storage_path"])
    await client.delete_object(report["storage_bucket"], report["storage_path"])
    try:
        await repository.delete(report_id)
    except Exception:
        try:
            await client.upload_object(
                report["storage_bucket"],
                report["storage_path"],
                original_content,
                report["mime_type"],
            )
        except Exception:
            logger.exception("Failed to restore a private report object after its database deletion failed.")
        raise
    await _audit(client, athlete_id, "MEDICAL_REPORT_DELETED", "medical_report", report_id)


@router.get("/biomarkers")
async def list_biomarkers(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    athlete_id, _, client = context
    measurements = await BiomarkerRepository(client, athlete_id).list_measurements()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for measurement in measurements:
        name = measurement.get("canonical_name") or measurement["biomarker_name"]
        grouped.setdefault(name, []).append(measurement)
    summaries = []
    for name, items in grouped.items():
        numeric_values = [item for item in items if item.get("value_numeric") is not None and item.get("unit") == items[0].get("unit")]
        trend = "INSUFFICIENT_DATA"
        trend_available = len(numeric_values) >= 2
        if trend_available:
            latest_value = float(numeric_values[0]["value_numeric"])
            previous_value = float(numeric_values[1]["value_numeric"])
            trend = "INCREASING" if latest_value > previous_value else "DECREASING" if latest_value < previous_value else "UNCHANGED"
        summaries.append(
            {
                "biomarker_name": items[0]["biomarker_name"],
                "canonical_name": items[0].get("canonical_name"),
                "latest": items[0],
                "measurement_count": len(items),
                "trend": trend,
                "trend_available": trend_available,
                "measurements": items,
            }
        )
    return success(
        request,
        {
            "biomarkers": summaries,
            "note": "Trend direction is descriptive only and is not a medical interpretation.",
        },
    )


@router.get("/biomarkers/{biomarker_name}")
async def get_biomarker(
    request: Request,
    biomarker_name: str,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    athlete_id, _, client = context
    measurements = await BiomarkerRepository(client, athlete_id).list_measurements()
    filtered = [
        item
        for item in measurements
        if (item.get("canonical_name") or item["biomarker_name"]).casefold() == biomarker_name.casefold()
    ]
    if not filtered:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No measurements were found for this biomarker.")
    values = [item for item in filtered if item.get("value_numeric") is not None]
    trend = "INSUFFICIENT_DATA"
    if len(values) >= 2 and values[0].get("unit") == values[1].get("unit"):
        latest_value = float(values[0]["value_numeric"])
        previous_value = float(values[1]["value_numeric"])
        trend = "INCREASING" if latest_value > previous_value else "DECREASING" if latest_value < previous_value else "UNCHANGED"
    return success(
        request,
        {
            "biomarker_name": filtered[0].get("canonical_name") or filtered[0]["biomarker_name"],
            "latest": filtered[0],
            "measurements": filtered,
            "trend": trend,
            "trend_available": trend != "INSUFFICIENT_DATA",
            "missing_value_label": None if values else "No numeric value was extracted.",
        },
    )


@router.get("/body-map")
async def get_body_map(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    athlete_id, _, client = context
    repository = BodyMapRepository(client, athlete_id)
    regions, findings = await _gather(repository.regions(), repository.findings())
    by_region: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        by_region.setdefault(str(finding["body_region_id"]), []).append(finding)
    response_regions = []
    now = datetime.now(UTC)
    for region in regions:
        region_findings = by_region.get(str(region["id"]), [])
        latest = region_findings[0] if region_findings else None
        if not latest:
            state = BodyFindingState.NO_DATA.value
        elif any(item.get("severity") == "REVIEW_RECOMMENDED" for item in region_findings):
            state = BodyFindingState.NEEDS_REVIEW.value
        else:
            created = datetime.fromisoformat(latest["created_at"].replace("Z", "+00:00"))
            state = (
                BodyFindingState.RECENT_FINDING.value
                if now - created <= timedelta(days=30)
                else BodyFindingState.HISTORICAL_FINDING.value
            )
        response_regions.append({**region, "state": state, "findings": region_findings})
    return success(request, {"regions": response_regions})


@router.post("/body-map/findings", status_code=status.HTTP_201_CREATED)
async def create_body_map_finding(
    request: Request,
    body: BodyRegionFindingCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    athlete_id, _, client = context
    repo = BodyMapRepository(client, athlete_id)
    if str(body.body_region_id) not in {str(region["id"]) for region in await repo.regions()}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The requested body region was not found.")
    records = await client.rest(
        "POST",
        "body_region_findings",
        payload={
            "athlete_id": str(athlete_id),
            "body_region_id": str(body.body_region_id),
            "finding_type": body.finding_type,
            "description": body.description,
            "source_type": "USER_ENTERED",
        },
        prefer="return=representation",
    )
    finding = records[0]
    await _audit(client, athlete_id, "BODY_MAP_NOTE_CREATED", "body_region_finding", UUID(finding["id"]))
    return success(request, {"finding": finding})


@router.get("/health-intelligence")
async def list_health_intelligence(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    items = await _health_repo(context).list_rows("health_intelligence_items")
    return success(
        request,
        {
            "items": items,
            "engine_status": "NOT_CONFIGURED",
            "notice": "No AI-generated health interpretations are available. This feature does not diagnose.",
        },
    )


@router.get("/nutrition/profile")
async def get_nutrition_profile(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    athlete_id, _, client = context
    rows = await client.rest(
        "GET",
        "nutrition_profiles",
        params={"athlete_id": f"eq.{athlete_id}", "select": "*", "limit": "1"},
    )
    profile = rows[0] if rows else {
        "athlete_id": str(athlete_id),
        "goal": "GENERAL_SPORTS_NUTRITION",
        "hydration_goal_ml": None,
        "updated_at": None,
    }
    return success(request, {"profile": profile})


@router.put("/nutrition/profile")
async def update_nutrition_profile(
    request: Request,
    body: NutritionProfileUpdate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    athlete_id, _, client = context
    repo = _health_repo(context)
    profile = await repo.upsert(
        "nutrition_profiles",
        {"goal": body.goal.value, "hydration_goal_ml": body.hydration_goal_ml},
        conflict="athlete_id",
    )
    await _audit(client, athlete_id, "NUTRITION_PROFILE_UPDATED", "nutrition_profile")
    return success(request, {"profile": profile})


@router.get("/nutrition/entries")
async def list_nutrition_entries(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    filters: dict[str, str] = {}
    if start_date:
        filters["entry_date"] = f"gte.{start_date.isoformat()}"
    if end_date:
        filters["entry_date"] = f"lte.{end_date.isoformat()}" if "entry_date" not in filters else filters["entry_date"]
        if start_date:
            filters["and"] = f"(entry_date.gte.{start_date.isoformat()},entry_date.lte.{end_date.isoformat()})"
    entries = await _health_repo(context).list_rows(
        "nutrition_entries",
        order="entry_date.desc,created_at.desc",
        filters=filters,
    )
    return success(request, {"entries": entries})


@router.post("/nutrition/entries", status_code=status.HTTP_201_CREATED)
async def create_nutrition_entry(
    request: Request,
    body: NutritionEntryCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    athlete_id, _, client = context
    entry = await _health_repo(context).insert(
        "nutrition_entries",
        body.model_dump(mode="json"),
    )
    await _audit(client, athlete_id, "NUTRITION_ENTRY_CREATED", "nutrition_entry", UUID(entry["id"]))
    return success(request, {"entry": entry})


@router.get("/medications")
async def list_medications(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    medications = await _health_repo(context).list_rows("medications", order="created_at.desc")
    return success(request, {"medications": medications})


@router.post("/medications", status_code=status.HTTP_201_CREATED)
async def create_medication(
    request: Request,
    body: MedicationCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    athlete_id, _, client = context
    values = body.model_dump(mode="json")
    if values["source_type"] != "USER_ENTERED":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only user-entered medications can be added from this endpoint.",
        )
    if values.get("medical_report_id"):
        report = await MedicalReportRepository(client, athlete_id).get(UUID(values["medical_report_id"]))
        if report is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The referenced report was not found.")
    medication = await _health_repo(context).insert("medications", values)
    await _audit(client, athlete_id, "MEDICATION_CREATED", "medication", UUID(medication["id"]))
    return success(request, {"medication": medication})


@router.patch("/medications/{medication_id}")
async def update_medication(
    request: Request,
    medication_id: UUID,
    body: MedicationUpdate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    athlete_id, _, client = context
    values = body.model_dump(exclude_unset=True, mode="json")
    if "name" in values and values["name"] is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Medication name cannot be empty.")
    medication = await _health_repo(context).patch("medications", medication_id, values)
    if medication is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The medication was not found.")
    await _audit(client, athlete_id, "MEDICATION_UPDATED", "medication", medication_id)
    return success(request, {"medication": medication})


@router.delete("/medications/{medication_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medication(
    medication_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> None:
    athlete_id, _, client = context
    repository = _health_repo(context)
    existing = await repository.list_rows(
        "medications",
        select="id",
        filters={"id": f"eq.{medication_id}"},
        limit=1,
    )
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The medication was not found.")
    await repository.delete("medications", medication_id)
    await _audit(client, athlete_id, "MEDICATION_DELETED", "medication", medication_id)


@router.get("/anti-doping")
async def get_anti_doping_status(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    reviews = await _health_repo(context).list_rows("anti_doping_reviews")
    return success(
        request,
        {
            "reviews": reviews,
            "status": reviews[0]["status"] if reviews else AntiDopingStatus.INSUFFICIENT_INFORMATION.value,
            "source_status": "NOT_CONFIGURED",
            "notice": "No current verified prohibited-list source is connected. This is not anti-doping clearance.",
        },
    )


@router.get("/skin-screening")
async def get_skin_screenings(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    _, settings, _ = context
    records = await _health_repo(context).list_rows(
        "skin_screenings",
        select="id,athlete_id,result,quality_status,consent_purpose,consented_at,source_type,retained_until,created_at",
    )
    return success(
        request,
        {
            "records": records,
            "feature_enabled": settings.skin_screening_enabled,
            "status": "NOT_CONFIGURED" if not settings.skin_screening_enabled else "MODEL_NOT_CONFIGURED",
            "diagnosis_available": False,
        },
    )


@router.get("/reports")
async def list_health_reports(
    request: Request,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    records = await _health_repo(context).list_rows("health_reports")
    return success(request, {"reports": records})


@router.get("/reports/{report_id}")
async def get_health_report(
    request: Request,
    report_id: UUID,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    records = await _health_repo(context).list_rows(
        "health_reports",
        filters={"id": f"eq.{report_id}"},
        limit=1,
    )
    if not records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The health report was not found.")
    return success(request, {"report": records[0]})


@router.post("/reports", status_code=status.HTTP_201_CREATED)
async def create_health_report(
    request: Request,
    body: HealthReportCreate,
    context: Annotated[AthleteContext, Depends(athlete_context)],
) -> dict:
    athlete_id, _, client = context
    health = _health_repo(context)
    verified = await _verify_health_report_sources(body, athlete_id, client)
    report = await health.insert(
        "health_reports",
        {
            "report_type": body.report_type,
            "source_ids": [str(item) for item in verified],
            "status": "DRAFT",
            "summary": None,
        },
    )
    await _audit(client, athlete_id, "HEALTH_REPORT_DRAFT_CREATED", "health_report", UUID(report["id"]))
    return success(request, {"report": report})


async def _verify_health_report_sources(
    body: HealthReportCreate,
    athlete_id: UUID,
    client: SupabaseRepository,
) -> list[UUID]:
    source_table = {
        "MEDICAL_REPORT_ANALYSIS": "medical_reports",
        "BIOMARKER_REPORT": "biomarker_measurements",
        "BODY_MAP_REPORT": "body_region_findings",
        "HEALTH_INTELLIGENCE_REPORT": "health_intelligence_items",
        "NUTRITION_REPORT": "nutrition_entries",
        "MEDICATION_REPORT": "medications",
        "ANTI_DOPING_REVIEW": "anti_doping_reviews",
        "SKIN_SCREENING_REPORT": "skin_screenings",
    }.get(body.report_type)
    if body.report_type == "FULL_HEALTH_REPORT":
        source_tables = [
            "medical_reports",
            "biomarker_measurements",
            "body_region_findings",
            "health_intelligence_items",
            "nutrition_entries",
            "medications",
            "anti_doping_reviews",
            "skin_screenings",
        ]
        found: set[UUID] = set()
        for table in source_tables:
            records = await client.rest(
                "GET",
                table,
                params={
                    "athlete_id": f"eq.{athlete_id}",
                    "id": f"in.({','.join(str(item) for item in body.source_ids)})",
                    "select": "id",
                },
            )
            found.update(UUID(record["id"]) for record in records)
    elif source_table:
        records = await client.rest(
            "GET",
            source_table,
            params={
                "athlete_id": f"eq.{athlete_id}",
                "id": f"in.({','.join(str(item) for item in body.source_ids)})",
                "select": "id",
            },
        )
        found = {UUID(record["id"]) for record in records}
    else:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="This report type is not supported.")
    if found != set(body.source_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more selected report sources were not found.",
        )
    return body.source_ids
