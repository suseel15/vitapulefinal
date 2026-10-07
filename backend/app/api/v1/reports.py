import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import Settings, get_settings
from app.core.responses import success
from app.core.security import bearer_scheme, require_roles
from app.repositories.supabase import SupabaseRepository
from app.reports.engine import ReportEngine
from app.reports.schemas import EmailReportRequest, ReportCreateResponse, ReportRequest, ReportStatus

router = APIRouter(prefix="/reports", tags=["reports"])
ReportContext = tuple[UUID, UUID, Settings, SupabaseRepository]


async def report_context(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    profile: Annotated[dict[str, Any], Depends(require_roles("ATHLETE"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReportContext:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    try:
        athlete_id = UUID(str(profile["id"]))
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="An athlete profile is required.") from error
    return athlete_id, athlete_id, settings, SupabaseRepository(settings, credentials.credentials, service_role=True)


def _engine(context: ReportContext) -> ReportEngine:
    _, _, settings, repository = context
    return ReportEngine(settings, repository)


async def _authorized_report(engine: ReportEngine, athlete_id: UUID, report_id: UUID) -> dict[str, Any]:
    try:
        return await engine._report(athlete_id, report_id)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.") from error


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=ReportCreateResponse, response_model_by_alias=True)
async def create_report(
    request: Request,
    body: ReportRequest,
    background_tasks: BackgroundTasks,
    context: Annotated[ReportContext, Depends(report_context)],
) -> dict[str, Any]:
    athlete_id, requested_by, _, _ = context
    engine = _engine(context)
    try:
        report_id, created = await engine.create(
            athlete_id=athlete_id,
            requested_by=requested_by,
            request=body,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    if created:
        background_tasks.add_task(
            engine.process,
            athlete_id=athlete_id,
            requested_by=requested_by,
            report_id=report_id,
            request=body,
        )
        report_status = ReportStatus.QUEUED
    else:
        record = await _authorized_report(engine, athlete_id, report_id)
        report_status = ReportStatus(record["status"])
    payload = ReportCreateResponse(
        reportId=report_id,
        status=report_status,
        statusUrl=str(request.url_for("get_report_status", report_id=str(report_id))),
    )
    return success(request, payload.model_dump(mode="json", by_alias=True))


@router.get("")
async def list_reports(
    request: Request,
    context: Annotated[ReportContext, Depends(report_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    athlete_id, _, _, repository = context
    rows = await repository.rest(
        "GET",
        "reports",
        params={
            "athlete_id": f"eq.{athlete_id}",
            "select": "id,report_type,title,status,summary,date_range_start,date_range_end,ai_status,html_status,pdf_status,email_status,report_version,created_at,completed_at,error_code",
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )
    return success(request, {"reports": rows if isinstance(rows, list) else []})


@router.get("/timeline")
async def report_timeline(
    request: Request,
    context: Annotated[ReportContext, Depends(report_context)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, Any]:
    athlete_id, _, _, repository = context
    events = await repository.rest(
        "GET",
        "athlete_timeline_events",
        params={
            "athlete_id": f"eq.{athlete_id}",
            "select": "id,event_type,source_type,source_id,event_time,title,summary,severity",
            "order": "event_time.desc",
            "limit": str(limit),
        },
    )
    return success(request, {"events": events if isinstance(events, list) else []})


@router.get("/intelligence")
async def athlete_intelligence(
    request: Request,
    context: Annotated[ReportContext, Depends(report_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    athlete_id, _, _, repository = context
    insights, snapshots = await asyncio.gather(
        repository.rest(
            "GET",
            "athlete_intelligence_insights",
            params={
                "athlete_id": f"eq.{athlete_id}",
                "select": "id,snapshot_id,period_start,period_end,insight_type,statement,source_ids,evidence_strength,status,interpretation_source,created_at",
                "order": "period_end.desc",
                "limit": str(limit),
            },
        ),
        repository.rest(
            "GET",
            "athlete_intelligence_snapshots",
            params={
                "athlete_id": f"eq.{athlete_id}",
                "select": "id,report_id,period_start,period_end,data_completeness,calculation_version,summary_json,created_at",
                "order": "period_end.desc",
                "limit": str(limit),
            },
        ),
    )
    return success(
        request,
        {
            "insights": insights if isinstance(insights, list) else [],
            "snapshots": snapshots if isinstance(snapshots, list) else [],
        },
    )


@router.get("/review-items")
async def list_review_items(
    request: Request,
    context: Annotated[ReportContext, Depends(report_context)],
    status_filter: Annotated[str | None, Query(alias="status", pattern="^(OPEN|ACKNOWLEDGED|RESOLVED|DISMISSED)$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    athlete_id, _, _, repository = context
    params = {
        "athlete_id": f"eq.{athlete_id}",
        "select": "id,insight_id,title,description,source_ids,status,created_at,updated_at",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    if status_filter:
        params["status"] = f"eq.{status_filter}"
    items = await repository.rest("GET", "review_items", params=params)
    return success(request, {"items": items if isinstance(items, list) else []})


@router.patch("/review-items/{item_id}")
async def update_review_item(
    request: Request,
    item_id: UUID,
    context: Annotated[ReportContext, Depends(report_context)],
    item_status: Annotated[Literal["ACKNOWLEDGED", "RESOLVED", "DISMISSED"], Body(embed=True, alias="status")],
) -> dict[str, Any]:
    athlete_id, _, _, repository = context
    rows = await repository.rest(
        "PATCH",
        "review_items",
        params={"id": f"eq.{item_id}", "athlete_id": f"eq.{athlete_id}", "select": "id,status,updated_at"},
        payload={"status": item_status, "updated_at": datetime.now(UTC).isoformat()},
        prefer="return=representation",
    )
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review item not found.")
    return success(request, {"item": rows[0]})


@router.get("/{report_id}/status", name="get_report_status")
async def get_report_status(
    request: Request,
    report_id: UUID,
    context: Annotated[ReportContext, Depends(report_context)],
) -> dict[str, Any]:
    athlete_id, requested_by, _, repository = context
    record = await _authorized_report(_engine(context), athlete_id, report_id)
    await repository.rest(
        "POST",
        "report_access_audit",
        payload={
            "athlete_id": str(athlete_id),
            "actor_id": str(requested_by),
            "report_id": str(report_id),
            "action": "REPORT_VIEWED",
        },
    )
    return success(
        request,
        {
            "reportId": str(report_id),
            "status": record["status"],
            "aiStatus": record["ai_status"],
            "htmlStatus": record["html_status"],
            "pdfStatus": record["pdf_status"],
            "emailStatus": record["email_status"],
            "errorCode": record["error_code"],
            "createdAt": record["created_at"],
            "completedAt": record["completed_at"],
        },
    )


@router.get("/{report_id}")
async def get_report(
    request: Request,
    report_id: UUID,
    context: Annotated[ReportContext, Depends(report_context)],
) -> dict[str, Any]:
    athlete_id, requested_by, _, repository = context
    record = await _authorized_report(_engine(context), athlete_id, report_id)
    await repository.rest(
        "POST",
        "report_access_audit",
        payload={
            "athlete_id": str(athlete_id),
            "actor_id": str(requested_by),
            "report_id": str(report_id),
            "action": "REPORT_VIEWED",
        },
    )
    return success(request, {"report": record.get("report_data", {})})


@router.get("/{report_id}/download")
async def download_report(
    request: Request,
    report_id: UUID,
    context: Annotated[ReportContext, Depends(report_context)],
    file_format: Annotated[Literal["pdf", "html"], Query(alias="format")] = "pdf",
) -> dict[str, Any]:
    athlete_id, requested_by, settings, repository = context
    record = await _authorized_report(_engine(context), athlete_id, report_id)
    if record["status"] != ReportStatus.COMPLETED.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The report is not ready to download.")
    files = await repository.rest(
        "GET",
        "report_files",
        params={
            "athlete_id": f"eq.{athlete_id}",
            "report_id": f"eq.{report_id}",
            "file_type": f"eq.{file_format.upper()}",
            "select": "storage_bucket,storage_path,mime_type,file_size,sha256",
            "limit": "1",
        },
    )
    if not isinstance(files, list) or not files:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="The requested report format is unavailable.")
    secure_url = await repository.signed_url(
        files[0]["storage_bucket"],
        files[0]["storage_path"],
        settings.report_signed_url_expiry_seconds,
    )
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.report_signed_url_expiry_seconds)
    await repository.rest(
        "POST",
        "report_access_audit",
        payload={
            "athlete_id": str(athlete_id),
            "actor_id": str(requested_by),
            "report_id": str(report_id),
            "action": "REPORT_DOWNLOADED",
        },
    )
    return success(
        request,
        {
            "url": secure_url,
            "mimeType": files[0]["mime_type"],
            "fileSize": files[0]["file_size"],
            "sha256": files[0]["sha256"],
            "expiresAt": expires_at.isoformat(),
            "expiresInSeconds": settings.report_signed_url_expiry_seconds,
        },
    )


@router.post("/{report_id}/email", status_code=status.HTTP_202_ACCEPTED)
async def email_report(
    request: Request,
    report_id: UUID,
    body: EmailReportRequest,
    background_tasks: BackgroundTasks,
    context: Annotated[ReportContext, Depends(report_context)],
) -> dict[str, Any]:
    athlete_id, requested_by, _, _ = context
    engine = _engine(context)
    try:
        delivery_id = await engine.queue_email(
            athlete_id=athlete_id,
            requested_by=requested_by,
            report_id=report_id,
            recipient=body.recipient,
        )
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    background_tasks.add_task(
        engine.process_email,
        athlete_id=athlete_id,
        requested_by=requested_by,
        report_id=report_id,
        delivery_id=delivery_id,
        recipient=body.recipient,
    )
    return success(request, {"deliveryId": str(delivery_id), "status": "QUEUED"})
