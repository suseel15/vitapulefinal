import asyncio
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import Settings, get_settings
from app.core.responses import success
from app.core.security import bearer_scheme, require_roles
from app.repositories.supabase import SupabaseRepository
from app.reports.engine import ReportEngine
from app.reports.schemas import EmailReportRequest, ReportRequest, ReportStatus, ReportType
from app.schemas.doctor import (
    CareGoalCreate,
    CareItemCreate,
    CarePlanCreate,
    CarePlanUpdate,
    DoctorNoteCreate,
    DoctorNoteUpdate,
    DoctorReviewCreate,
    DoctorProfileUpdate,
    InvitationCreate,
    InvitationResponse,
    MessageCreate,
    RehabProgramAssignment,
)
from app.services.doctor_service import DoctorService

router = APIRouter(prefix="/doctor", tags=["doctor"])
athlete_router = APIRouter(prefix="/care-team", tags=["care-team"])
DoctorIdentity = tuple[UUID, dict[str, Any], Settings, SupabaseRepository]
AthleteIdentity = tuple[UUID, dict[str, Any], SupabaseRepository]


async def doctor_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    profile: Annotated[dict[str, Any], Depends(require_roles("DOCTOR"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DoctorIdentity:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        doctor_id = UUID(str(profile["id"]))
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=403, detail="A doctor profile is required.") from error
    repository = SupabaseRepository(settings, credentials.credentials, service_role=True)
    rows = await repository.rest(
        "GET",
        "doctor_profiles",
        params={
            "id": f"eq.{doctor_id}",
            "select": "id,full_name,professional_title,specialization,license_region,license_id,clinic_name,clinic_address,years_experience,sports_specialties,profile_photo_path,verification_status,account_status,phone,verified_at",
            "limit": "1",
        },
    )
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=403, detail="A doctor profile is required.")
    return doctor_id, rows[0], settings, repository


async def active_doctor(
    identity: Annotated[DoctorIdentity, Depends(doctor_identity)],
) -> DoctorIdentity:
    _, doctor, _, _ = identity
    if doctor["verification_status"] != "VERIFIED":
        raise HTTPException(status_code=403, detail="Doctor verification is required before clinical access.")
    if doctor["account_status"] != "ACTIVE":
        raise HTTPException(status_code=403, detail="This doctor account is not active.")
    return identity


async def athlete_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    profile: Annotated[dict[str, Any], Depends(require_roles("ATHLETE"))],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AthleteIdentity:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        athlete_id = UUID(str(profile["id"]))
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=403, detail="An athlete profile is required.") from error
    return athlete_id, profile, SupabaseRepository(settings, credentials.credentials, service_role=True)


def _service(identity: DoctorIdentity) -> DoctorService:
    return DoctorService(identity[3], identity[0])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get("/identity")
async def get_doctor_identity(
    request: Request,
    identity: Annotated[DoctorIdentity, Depends(doctor_identity)],
) -> dict[str, Any]:
    doctor_id, doctor, _, repository = identity
    profiles = await repository.rest(
        "GET",
        "profiles",
        params={"id": f"eq.{doctor_id}", "select": "id,display_name", "limit": "1"},
    )
    doctor["display_name"] = profiles[0].get("display_name", "") if isinstance(profiles, list) and profiles else ""
    return success(request, {"doctor": doctor})


@router.patch("/profile")
async def update_doctor_profile(
    request: Request,
    body: DoctorProfileUpdate,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    doctor_id, _, _, repository = identity
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Provide at least one profile field to update.")
    if "full_name" in updates:
        updates["full_name"] = updates["full_name"].strip()
        if not updates["full_name"]:
            raise HTTPException(status_code=422, detail="Doctor name cannot be empty.")
    rows = await repository.rest(
        "PATCH",
        "doctor_profiles",
        params={"id": f"eq.{doctor_id}", "select": "*"},
        payload=updates,
        prefer="return=representation",
    )
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=409, detail="Doctor profile could not be updated.")
    await repository.rest(
        "PATCH",
        "profiles",
        params={"id": f"eq.{doctor_id}"},
        payload={"display_name": updates["full_name"]} if "full_name" in updates else {},
    )
    return success(request, {"doctor": rows[0]})


@router.get("/dashboard")
async def dashboard(
    request: Request,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    doctor_id, _, _, repository = identity
    service = _service(identity)
    relationships, tasks, plans, notifications, reports = await asyncio.gather(
        service.rows(
            "doctor_athlete_relationships",
            {"doctor_id": f"eq.{doctor_id}", "status": "eq.ACTIVE", "select": "athlete_id", "limit": "1000"},
        ),
        service.rows(
            "review_tasks",
            {"doctor_id": f"eq.{doctor_id}", "status": "in.(OPEN,IN_PROGRESS)", "select": "id,athlete_id,task_type,priority,title,status,due_at,created_at", "order": "due_at.asc.nullslast", "limit": "10"},
        ),
        service.rows(
            "care_plans",
            {"doctor_id": f"eq.{doctor_id}", "status": "in.(ACTIVE,REVIEW_REQUIRED)", "select": "id,athlete_id,title,status,target_review_date,updated_at", "order": "target_review_date.asc.nullslast", "limit": "100"},
        ),
        service.rows(
            "doctor_notifications",
            {"recipient_id": f"eq.{doctor_id}", "read_at": "is.null", "select": "id,notification_type,title,body,created_at", "order": "created_at.desc", "limit": "5"},
        ),
        service.rows(
            "reports",
            {"created_by": f"eq.{doctor_id}", "select": "id,athlete_id,report_type,title,status,created_at", "order": "created_at.desc", "limit": "5"},
        ),
    )
    athlete_ids = [row["athlete_id"] for row in relationships]
    return success(
        request,
        {
            "counts": {
                "active_athletes": len(athlete_ids),
                "pending_reviews": len(tasks),
                "active_care_plans": len(plans),
                "unread_notifications": len(notifications),
                "recent_doctor_reports": len(reports),
            },
            "review_tasks": tasks,
            "care_plans_due": plans,
            "notifications": notifications,
            "recent_reports": reports,
            "progress": {"improving": None, "stable": None, "variable": None, "declining": None, "insufficient_data": None},
            "progress_message": "Progress categories are not summarized until comparable source data is available.",
            "safety": {"configured": False, "unresolved_incidents": None},
            "last_updated": datetime.now(UTC).isoformat(),
        },
    )


@router.get("/athletes")
async def list_connected_athletes(
    request: Request,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
    search: Annotated[str, Query(max_length=120)] = "",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, Any]:
    rows, total = await _service(identity).list_athletes(query=search.strip(), offset=offset, limit=limit)
    return success(request, {"athletes": rows, "pagination": {"offset": offset, "limit": limit, "total": total}})


@router.post("/invitations", status_code=status.HTTP_201_CREATED)
async def invite_athlete(
    request: Request,
    body: InvitationCreate,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    invitation = await _service(identity).invite(body, request_id=_request_id(request))
    return success(request, {"invitation": invitation})


@router.get("/invitations")
async def list_sent_invitations(
    request: Request,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    doctor_id, _, _, repository = identity
    invitations = await repository.rest(
        "GET",
        "doctor_athlete_invitations",
        params={
            "doctor_id": f"eq.{doctor_id}", "select": "id,athlete_id,email,status,relationship_type,message,created_at,expires_at,responded_at",
            "order": "created_at.desc", "limit": str(limit),
        },
    )
    return success(request, {"invitations": invitations if isinstance(invitations, list) else []})


@router.get("/athletes/{athlete_id}")
async def get_athlete_overview(
    request: Request,
    athlete_id: UUID,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    return success(request, {"overview": await _service(identity).athlete_overview(athlete_id)})


@router.get("/athletes/{athlete_id}/records/{domain}")
async def get_athlete_domain_records(
    request: Request,
    athlete_id: UUID,
    domain: Literal["health", "reports", "rehab", "movement", "recovery", "wellbeing", "safety", "intelligence"],
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    records = await _service(identity).records(athlete_id, domain, limit)
    return success(request, records)


@router.get("/athletes/{athlete_id}/timeline")
async def athlete_timeline(
    request: Request,
    athlete_id: UUID,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, Any]:
    service = _service(identity)
    await service.require_relationship(athlete_id)
    rows = await service.rows(
        "athlete_timeline_events",
        {
            "athlete_id": f"eq.{athlete_id}",
            "select": "id,event_type,source_type,source_id,event_time,title,summary,severity,actor_type,actor_id,related_entity_type,related_entity_id",
            "order": "event_time.desc",
            "limit": str(limit),
        },
    )
    return success(request, {"events": rows, "last_updated": datetime.now(UTC).isoformat()})


@router.get("/athletes/{athlete_id}/care-plans")
async def list_care_plans(
    request: Request,
    athlete_id: UUID,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    service = _service(identity)
    await service.require_relationship(athlete_id)
    plans = await service.rows(
        "care_plans",
        {"athlete_id": f"eq.{athlete_id}", "doctor_id": f"eq.{identity[0]}", "select": "*", "order": "updated_at.desc", "limit": "100"},
    )
    return success(request, {"care_plans": plans})


@router.post("/athletes/{athlete_id}/care-plans", status_code=status.HTTP_201_CREATED)
async def create_care_plan(
    request: Request,
    athlete_id: UUID,
    body: CarePlanCreate,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    plan = await _service(identity).create_plan(athlete_id, body, _request_id(request))
    return success(request, {"care_plan": plan})


@router.get("/athletes/{athlete_id}/care-plans/{plan_id}")
async def get_care_plan(
    request: Request,
    athlete_id: UUID,
    plan_id: UUID,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    service = _service(identity)
    plan = await service._owned_plan(athlete_id, plan_id)
    goals, items, versions = await asyncio.gather(
        service.rows("care_plan_goals", {"care_plan_id": f"eq.{plan_id}", "athlete_id": f"eq.{athlete_id}", "select": "*", "limit": "200"}),
        service.rows("care_plan_items", {"care_plan_id": f"eq.{plan_id}", "athlete_id": f"eq.{athlete_id}", "select": "*", "order": "created_at.desc", "limit": "200"}),
        service.rows("care_plan_versions", {"care_plan_id": f"eq.{plan_id}", "athlete_id": f"eq.{athlete_id}", "select": "version_number,created_by,change_summary,created_at,snapshot", "order": "version_number.desc", "limit": "100"}),
    )
    return success(request, {"care_plan": plan, "goals": goals, "items": items, "versions": versions})


@router.patch("/athletes/{athlete_id}/care-plans/{plan_id}")
async def update_care_plan(
    request: Request,
    athlete_id: UUID,
    plan_id: UUID,
    body: CarePlanUpdate,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    plan = await _service(identity).update_plan(athlete_id, plan_id, body, _request_id(request))
    return success(request, {"care_plan": plan})


@router.post("/athletes/{athlete_id}/care-plans/{plan_id}/goals", status_code=status.HTTP_201_CREATED)
async def add_care_goal(
    request: Request,
    athlete_id: UUID,
    plan_id: UUID,
    body: CareGoalCreate,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    goal = await _service(identity).add_goal(athlete_id, plan_id, body)
    return success(request, {"goal": goal})


@router.post("/athletes/{athlete_id}/care-plans/{plan_id}/items", status_code=status.HTTP_201_CREATED)
async def add_care_plan_item(
    request: Request,
    athlete_id: UUID,
    plan_id: UUID,
    body: CareItemCreate,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    item = await _service(identity).add_item(athlete_id, plan_id, body, _request_id(request))
    return success(request, {"item": item})


@router.post("/athletes/{athlete_id}/care-plans/{plan_id}/programs", status_code=status.HTTP_201_CREATED)
async def assign_rehab_program(
    request: Request,
    athlete_id: UUID,
    plan_id: UUID,
    body: RehabProgramAssignment,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    result = await _service(identity).assign_program(athlete_id, plan_id, body, _request_id(request))
    return success(request, result)


@router.get("/athletes/{athlete_id}/notes")
async def list_doctor_notes(
    request: Request,
    athlete_id: UUID,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    service = _service(identity)
    await service.require_relationship(athlete_id)
    notes = await service.rows(
        "doctor_notes",
        {"athlete_id": f"eq.{athlete_id}", "doctor_id": f"eq.{identity[0]}", "select": "id,note_type,title,content,visibility,version,created_at,updated_at", "order": "updated_at.desc", "limit": "100"},
    )
    return success(request, {"notes": notes})


@router.post("/athletes/{athlete_id}/notes", status_code=status.HTTP_201_CREATED)
async def create_doctor_note(
    request: Request,
    athlete_id: UUID,
    body: DoctorNoteCreate,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    note = await _service(identity).create_note(athlete_id, body, _request_id(request))
    return success(request, {"note": note})


@router.patch("/athletes/{athlete_id}/notes/{note_id}")
async def update_doctor_note(
    request: Request,
    athlete_id: UUID,
    note_id: UUID,
    body: DoctorNoteUpdate,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    note = await _service(identity).update_note(athlete_id, note_id, body, _request_id(request))
    return success(request, {"note": note})


@router.get("/athletes/{athlete_id}/reviews")
async def list_doctor_reviews(
    request: Request,
    athlete_id: UUID,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    service = _service(identity)
    await service.require_relationship(athlete_id)
    reviews = await service.rows(
        "doctor_reviews",
        {"athlete_id": f"eq.{athlete_id}", "doctor_id": f"eq.{identity[0]}", "select": "*", "order": "created_at.desc", "limit": "100"},
    )
    return success(request, {"reviews": reviews})


@router.post("/athletes/{athlete_id}/reviews", status_code=status.HTTP_201_CREATED)
async def create_doctor_review(
    request: Request,
    athlete_id: UUID,
    body: DoctorReviewCreate,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    review = await _service(identity).create_review(athlete_id, body, _request_id(request))
    return success(request, {"review": review})


@router.get("/review-tasks")
async def list_review_tasks(
    request: Request,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
    task_status: Annotated[str | None, Query(alias="status", pattern="^(OPEN|IN_PROGRESS|COMPLETED|DISMISSED|EXPIRED)$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    params = {
        "doctor_id": f"eq.{identity[0]}", "select": "*",
        "order": "due_at.asc.nullslast", "limit": str(limit),
    }
    if task_status:
        params["status"] = f"eq.{task_status}"
    tasks = await _service(identity).rows("review_tasks", params)
    return success(request, {"review_tasks": tasks})


@router.patch("/review-tasks/{task_id}")
async def update_review_task(
    request: Request,
    task_id: UUID,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
    task_status: Annotated[Literal["IN_PROGRESS", "COMPLETED", "DISMISSED"], Body(embed=True, alias="status")],
) -> dict[str, Any]:
    doctor_id, _, _, repository = identity
    rows = await repository.rest(
        "PATCH",
        "review_tasks",
        params={"id": f"eq.{task_id}", "doctor_id": f"eq.{doctor_id}", "select": "*"},
        payload={
            "status": task_status,
            "completed_at": datetime.now(UTC).isoformat() if task_status == "COMPLETED" else None,
        },
        prefer="return=representation",
    )
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=404, detail="Review task was not found.")
    await _service(identity).audit(
        doctor_id, UUID(rows[0]["athlete_id"]), "REVIEW_TASK_UPDATED", "REVIEW_TASK", task_id, _request_id(request)
    )
    return success(request, {"review_task": rows[0]})


@router.get("/notifications")
async def list_doctor_notifications(
    request: Request,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    notifications = await _service(identity).rows(
        "doctor_notifications",
        {"recipient_id": f"eq.{identity[0]}", "select": "id,notification_type,title,body,resource_type,resource_id,read_at,created_at", "order": "created_at.desc", "limit": str(limit)},
    )
    return success(request, {"notifications": notifications})


@router.get("/athletes/{athlete_id}/messages")
async def list_messages(
    request: Request,
    athlete_id: UUID,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    service = _service(identity)
    await service.require_relationship(athlete_id)
    threads = await service.rows(
        "message_threads",
        {"doctor_id": f"eq.{identity[0]}", "athlete_id": f"eq.{athlete_id}", "select": "id", "limit": "1"},
    )
    if not threads:
        return success(request, {"thread": None, "messages": []})
    messages = await service.rows(
        "messages",
        {"thread_id": f"eq.{threads[0]['id']}", "athlete_id": f"eq.{athlete_id}", "select": "id,thread_id,sender_id,message_type,body,created_at,read_at", "order": "created_at.asc", "limit": "200"},
    )
    return success(request, {"thread": threads[0], "messages": messages})


@router.post("/athletes/{athlete_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_message(
    request: Request,
    athlete_id: UUID,
    body: MessageCreate,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    result = await _service(identity).send_message(athlete_id, body, _request_id(request))
    return success(request, result)


@router.post("/athletes/{athlete_id}/reports", status_code=status.HTTP_202_ACCEPTED)
async def create_doctor_report(
    request: Request,
    athlete_id: UUID,
    body: ReportRequest,
    background_tasks: BackgroundTasks,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    await _service(identity).require_relationship(athlete_id)
    if body.report_type not in {
        ReportType.DOCTOR_ATHLETE_REPORT,
        ReportType.FULL_ATHLETE_REPORT,
        ReportType.WEEKLY_ATHLETE_REPORT,
        ReportType.MONTHLY_ATHLETE_REPORT,
    }:
        raise HTTPException(status_code=422, detail="This report type is not available in the doctor workspace.")
    doctor_id, _, settings, repository = identity
    engine = ReportEngine(settings, repository)
    try:
        report_id, created = await engine.create(
            athlete_id=athlete_id, requested_by=doctor_id, request=body
        )
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    if created:
        background_tasks.add_task(
            engine.process,
            athlete_id=athlete_id,
            requested_by=doctor_id,
            report_id=report_id,
            request=body,
        )
        await _service(identity).audit(doctor_id, athlete_id, "DOCTOR_REPORT_REQUESTED", "REPORT", report_id, _request_id(request))
    return success(request, {"report_id": str(report_id), "status": "QUEUED" if created else "EXISTING"})


@router.get("/athletes/{athlete_id}/reports")
async def list_doctor_reports(
    request: Request,
    athlete_id: UUID,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    service = _service(identity)
    await service.require_relationship(athlete_id)
    reports = await service.rows(
        "reports",
        {"athlete_id": f"eq.{athlete_id}", "select": "id,created_by,report_type,title,status,summary,ai_status,html_status,pdf_status,report_version,created_at,completed_at", "order": "created_at.desc", "limit": "100"},
    )
    return success(request, {"reports": reports})


@router.get("/athletes/{athlete_id}/reports/{report_id}")
async def get_doctor_report(
    request: Request,
    athlete_id: UUID,
    report_id: UUID,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    doctor_id, _, _, repository = identity
    await _service(identity).require_relationship(athlete_id)
    rows = await repository.rest(
        "GET", "reports",
        params={"id": f"eq.{report_id}", "athlete_id": f"eq.{athlete_id}", "select": "*", "limit": "1"},
    )
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=404, detail="Report was not found.")
    report = rows[0]
    await _service(identity).audit(doctor_id, athlete_id, "REPORT_VIEWED", "REPORT", report_id, _request_id(request))
    return success(request, {"report": report.get("report_data", {})})


@router.get("/athletes/{athlete_id}/reports/{report_id}/download")
async def download_doctor_report(
    request: Request,
    athlete_id: UUID,
    report_id: UUID,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
    file_format: Annotated[Literal["pdf", "html"], Query(alias="format")] = "pdf",
) -> dict[str, Any]:
    doctor_id, _, settings, repository = identity
    service = _service(identity)
    await service.require_relationship(athlete_id)
    reports = await service.rows(
        "reports", {"id": f"eq.{report_id}", "athlete_id": f"eq.{athlete_id}", "select": "id,status", "limit": "1"}
    )
    if not reports:
        raise HTTPException(status_code=404, detail="Report was not found.")
    if reports[0]["status"] != ReportStatus.COMPLETED.value:
        raise HTTPException(status_code=409, detail="The report is not ready to download.")
    files = await service.rows(
        "report_files",
        {"report_id": f"eq.{report_id}", "athlete_id": f"eq.{athlete_id}", "file_type": f"eq.{file_format.upper()}", "select": "storage_bucket,storage_path,mime_type,file_size,sha256", "limit": "1"},
    )
    if not files:
        raise HTTPException(status_code=404, detail="The requested report format is unavailable.")
    signed_url = await repository.signed_url(
        files[0]["storage_bucket"], files[0]["storage_path"], settings.report_signed_url_expiry_seconds
    )
    await service.audit(doctor_id, athlete_id, "REPORT_DOWNLOADED", "REPORT", report_id, _request_id(request))
    return success(
        request,
        {
            "url": signed_url,
            "mimeType": files[0]["mime_type"],
            "sha256": files[0]["sha256"],
            "expiresInSeconds": settings.report_signed_url_expiry_seconds,
        },
    )


@router.post("/athletes/{athlete_id}/reports/{report_id}/email", status_code=status.HTTP_202_ACCEPTED)
async def email_doctor_report(
    request: Request,
    athlete_id: UUID,
    report_id: UUID,
    body: EmailReportRequest,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    service = _service(identity)
    await service.require_relationship(athlete_id)
    reports = await service.rows(
        "reports", {"id": f"eq.{report_id}", "athlete_id": f"eq.{athlete_id}", "select": "id,status", "limit": "1"}
    )
    if not reports:
        raise HTTPException(status_code=404, detail="Report was not found.")
    engine = ReportEngine(identity[2], identity[3])
    try:
        delivery_id = await engine.queue_email(
            athlete_id=athlete_id, requested_by=identity[0], report_id=report_id, recipient=body.recipient
        )
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=409, detail="The report cannot be emailed yet.") from error
    await service.audit(identity[0], athlete_id, "REPORT_EMAILED", "REPORT", report_id, _request_id(request))
    return success(request, {"delivery_id": str(delivery_id), "status": "QUEUED"})


@router.get("/preferences")
async def get_dashboard_preferences(
    request: Request,
    identity: Annotated[DoctorIdentity, Depends(active_doctor)],
) -> dict[str, Any]:
    rows = await _service(identity).rows(
        "doctor_dashboard_preferences",
        {"doctor_id": f"eq.{identity[0]}", "select": "preferences,notification_preferences,updated_at", "limit": "1"},
    )
    return success(request, {"preferences": rows[0] if rows else {"preferences": {}, "notification_preferences": {}}})


@athlete_router.get("/invitations")
async def athlete_invitations(
    request: Request,
    identity: Annotated[AthleteIdentity, Depends(athlete_identity)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    athlete_id, _, repository = identity
    invitations = await repository.rest(
        "GET",
        "doctor_athlete_invitations",
        params={
            "athlete_id": f"eq.{athlete_id}", "status": "eq.PENDING",
            "expires_at": f"gt.{datetime.now(UTC).isoformat()}",
            "select": "id,doctor_id,relationship_type,message,created_at,expires_at",
            "order": "created_at.desc", "limit": str(limit),
        },
    )
    rows = invitations if isinstance(invitations, list) else []
    doctors: list[dict[str, Any]] = []
    if rows:
        ids = list(dict.fromkeys(item["doctor_id"] for item in rows))
        profiles = await repository.rest(
            "GET",
            "doctor_profiles",
            params={"id": f"in.({','.join(ids)})", "select": "id,full_name,professional_title,specialization,clinic_name,verification_status", "limit": str(limit)},
        )
        doctors = profiles if isinstance(profiles, list) else []
    doctor_map = {doctor["id"]: doctor for doctor in doctors}
    return success(request, {"invitations": [{**row, "doctor": doctor_map.get(row["doctor_id"])} for row in rows]})


@athlete_router.post("/invitations/{invitation_id}/respond")
async def respond_to_invitation(
    request: Request,
    invitation_id: UUID,
    body: InvitationResponse,
    identity: Annotated[AthleteIdentity, Depends(athlete_identity)],
) -> dict[str, Any]:
    athlete_id, _, repository = identity
    result = await repository.rpc(
        "respond_to_doctor_invitation",
        {"p_invitation_id": str(invitation_id), "p_athlete_id": str(athlete_id), "p_accept": body.accept},
    )
    return success(request, {"invitation": result})


@athlete_router.get("/relationships")
async def athlete_relationships(
    request: Request,
    identity: Annotated[AthleteIdentity, Depends(athlete_identity)],
) -> dict[str, Any]:
    athlete_id, _, repository = identity
    relationships = await repository.rest(
        "GET",
        "doctor_athlete_relationships",
        params={"athlete_id": f"eq.{athlete_id}", "select": "id,doctor_id,status,relationship_type,granted_at,created_at", "order": "created_at.desc", "limit": "100"},
    )
    rows = relationships if isinstance(relationships, list) else []
    doctor_ids = list(dict.fromkeys(row["doctor_id"] for row in rows))
    doctors = await repository.rest(
        "GET",
        "doctor_profiles",
        params={"id": f"in.({','.join(doctor_ids)})", "select": "id,full_name,professional_title,specialization,clinic_name,verification_status", "limit": "100"},
    ) if doctor_ids else []
    doctor_map = {doctor["id"]: doctor for doctor in doctors if isinstance(doctors, list)}
    return success(request, {"relationships": [{**row, "doctor": doctor_map.get(row["doctor_id"])} for row in rows]})


@athlete_router.post("/relationships/{relationship_id}/revoke")
async def revoke_relationship(
    request: Request,
    relationship_id: UUID,
    identity: Annotated[AthleteIdentity, Depends(athlete_identity)],
) -> dict[str, Any]:
    athlete_id, _, repository = identity
    rows = await repository.rest(
        "PATCH",
        "doctor_athlete_relationships",
        params={"id": f"eq.{relationship_id}", "athlete_id": f"eq.{athlete_id}", "status": "eq.ACTIVE", "select": "*"},
        payload={"status": "REVOKED", "revoked_at": datetime.now(UTC).isoformat()},
        prefer="return=representation",
    )
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=404, detail="Active care-team relationship was not found.")
    row = rows[0]
    service = DoctorService(repository, UUID(row["doctor_id"]))
    await service.notification(
        recipient_id=UUID(row["doctor_id"]), actor_id=athlete_id, athlete_id=athlete_id,
        notification_type="RELATIONSHIP_REVOKED", title="Care-team access updated",
        body="An athlete changed a VitaPulse care-team connection.",
        resource_type="RELATIONSHIP", resource_id=relationship_id,
    )
    await service.audit(athlete_id, athlete_id, "RELATIONSHIP_REVOKED", "RELATIONSHIP", relationship_id, _request_id(request))
    return success(request, {"relationship": row})


@athlete_router.get("/care-plans")
async def athlete_care_plans(
    request: Request,
    identity: Annotated[AthleteIdentity, Depends(athlete_identity)],
) -> dict[str, Any]:
    athlete_id, _, repository = identity
    plans = await repository.rest(
        "GET", "care_plans",
        params={"athlete_id": f"eq.{athlete_id}", "status": "not.in.(CANCELLED,ARCHIVED)", "select": "*", "order": "updated_at.desc", "limit": "100"},
    )
    plans = plans if isinstance(plans, list) else []
    items = await repository.rest(
        "GET", "care_plan_items",
        params={"athlete_id": f"eq.{athlete_id}", "status": "not.eq.CANCELLED", "select": "id,care_plan_id,item_type,title,description,linked_entity,rehab_program_id,sets,repetitions,duration_seconds,frequency,rest_seconds,intensity,instructions,restrictions,due_date,review_date,status,created_at", "order": "created_at.desc", "limit": "200"},
    )
    goals = await repository.rest(
        "GET", "care_plan_goals",
        params={"athlete_id": f"eq.{athlete_id}", "select": "id,care_plan_id,title,description,priority,target_date,status,measurement_type,target_value,current_value", "order": "created_at.asc", "limit": "200"},
    )
    return success(request, {"care_plans": plans, "items": items if isinstance(items, list) else [], "goals": goals if isinstance(goals, list) else []})


@athlete_router.patch("/care-plan-items/{item_id}")
async def athlete_update_care_item(
    request: Request,
    item_id: UUID,
    identity: Annotated[AthleteIdentity, Depends(athlete_identity)],
    item_status: Annotated[Literal["IN_PROGRESS", "COMPLETED"], Body(embed=True, alias="status")],
) -> dict[str, Any]:
    athlete_id, _, repository = identity
    rows = await repository.rest(
        "PATCH",
        "care_plan_items",
        params={"id": f"eq.{item_id}", "athlete_id": f"eq.{athlete_id}", "status": "in.(ASSIGNED,IN_PROGRESS)", "select": "*"},
        payload={"status": item_status, "completed_at": datetime.now(UTC).isoformat() if item_status == "COMPLETED" else None},
        prefer="return=representation",
    )
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=404, detail="Open care plan item was not found.")
    item = rows[0]
    service = DoctorService(repository, UUID(item["assigned_by"]))
    await service.audit(athlete_id, athlete_id, "CARE_PLAN_ITEM_COMPLETED" if item_status == "COMPLETED" else "CARE_PLAN_ITEM_STARTED", "CARE_PLAN_ITEM", item_id, _request_id(request))
    if item_status == "COMPLETED":
        await service.create_task(
            athlete_id=athlete_id, task_type="CARE_PLAN_ITEM_REVIEW",
            priority="LOW", subject_type="CARE_PLAN_ITEM", subject_id=item_id,
            title="Review completed care plan assignment",
            description="An athlete marked a care plan assignment complete.",
        )
    return success(request, {"item": item})


@athlete_router.get("/notes")
async def athlete_visible_doctor_notes(
    request: Request,
    identity: Annotated[AthleteIdentity, Depends(athlete_identity)],
) -> dict[str, Any]:
    athlete_id, _, repository = identity
    notes = await repository.rest(
        "GET", "doctor_notes",
        params={"athlete_id": f"eq.{athlete_id}", "visibility": "eq.ATHLETE_VISIBLE", "select": "id,doctor_id,note_type,title,content,version,created_at,updated_at", "order": "updated_at.desc", "limit": "100"},
    )
    return success(request, {"notes": notes if isinstance(notes, list) else []})


@athlete_router.get("/notifications")
async def athlete_notifications(
    request: Request,
    identity: Annotated[AthleteIdentity, Depends(athlete_identity)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> dict[str, Any]:
    athlete_id, _, repository = identity
    rows = await repository.rest(
        "GET", "doctor_notifications",
        params={"recipient_id": f"eq.{athlete_id}", "select": "id,notification_type,title,body,resource_type,resource_id,read_at,created_at", "order": "created_at.desc", "limit": str(limit)},
    )
    return success(request, {"notifications": rows if isinstance(rows, list) else []})


@athlete_router.get("/messages/{doctor_id}")
async def athlete_messages(
    request: Request,
    doctor_id: UUID,
    identity: Annotated[AthleteIdentity, Depends(athlete_identity)],
) -> dict[str, Any]:
    athlete_id, _, repository = identity
    relations = await repository.rest(
        "GET", "doctor_athlete_relationships",
        params={"doctor_id": f"eq.{doctor_id}", "athlete_id": f"eq.{athlete_id}", "status": "eq.ACTIVE", "select": "id", "limit": "1"},
    )
    if not isinstance(relations, list) or not relations:
        raise HTTPException(status_code=403, detail="Active care-team access is required.")
    threads = await repository.rest(
        "GET", "message_threads",
        params={"doctor_id": f"eq.{doctor_id}", "athlete_id": f"eq.{athlete_id}", "select": "id", "limit": "1"},
    )
    if not isinstance(threads, list) or not threads:
        return success(request, {"thread": None, "messages": []})
    messages = await repository.rest(
        "GET", "messages",
        params={"thread_id": f"eq.{threads[0]['id']}", "athlete_id": f"eq.{athlete_id}", "select": "id,thread_id,sender_id,message_type,body,created_at,read_at", "order": "created_at.asc", "limit": "200"},
    )
    return success(request, {"thread": threads[0], "messages": messages if isinstance(messages, list) else []})


@athlete_router.post("/messages/{doctor_id}", status_code=status.HTTP_201_CREATED)
async def athlete_send_message(
    request: Request,
    doctor_id: UUID,
    body: MessageCreate,
    identity: Annotated[AthleteIdentity, Depends(athlete_identity)],
) -> dict[str, Any]:
    athlete_id, _, repository = identity
    relations = await repository.rest(
        "GET", "doctor_athlete_relationships",
        params={"doctor_id": f"eq.{doctor_id}", "athlete_id": f"eq.{athlete_id}", "status": "eq.ACTIVE", "select": "id", "limit": "1"},
    )
    if not isinstance(relations, list) or not relations:
        raise HTTPException(status_code=403, detail="Active care-team access is required.")
    service = DoctorService(repository, doctor_id)
    result = await service.send_message(athlete_id, body, _request_id(request))
    result["message"]["sender_id"] = str(athlete_id)
    return success(request, result)


@athlete_router.post("/reports/{report_id}/comments", status_code=status.HTTP_201_CREATED)
async def athlete_report_comment(
    request: Request,
    report_id: UUID,
    comment: Annotated[str, Body(embed=True, min_length=1, max_length=4000)],
    identity: Annotated[AthleteIdentity, Depends(athlete_identity)],
) -> dict[str, Any]:
    athlete_id, _, repository = identity
    report_rows = await repository.rest(
        "GET", "reports", params={"id": f"eq.{report_id}", "athlete_id": f"eq.{athlete_id}", "select": "id,created_by", "limit": "1"}
    )
    if not isinstance(report_rows, list) or not report_rows:
        raise HTTPException(status_code=404, detail="Report was not found.")
    created_by = UUID(report_rows[0]["created_by"])
    access = await repository.rest(
        "GET", "doctor_athlete_relationships",
        params={"doctor_id": f"eq.{created_by}", "athlete_id": f"eq.{athlete_id}", "status": "eq.ACTIVE", "select": "id", "limit": "1"},
    )
    if not isinstance(access, list) or not access:
        raise HTTPException(status_code=403, detail="Active report-sharing access is required.")
    service = DoctorService(repository, created_by)
    return success(request, {"comment": await service.insert(
        "doctor_report_comments",
        {"athlete_id": str(athlete_id), "report_id": str(report_id), "doctor_id": str(created_by), "section": "ATHLETE_COMMENT", "comment": comment.strip()},
    )})
