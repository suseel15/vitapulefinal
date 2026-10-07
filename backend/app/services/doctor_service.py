import asyncio
import logging
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.repositories.supabase import SupabaseRepository
from app.schemas.doctor import (
    CareGoalCreate,
    CareItemCreate,
    CarePlanCreate,
    CarePlanUpdate,
    DoctorNoteCreate,
    DoctorNoteUpdate,
    DoctorReviewCreate,
    InvitationCreate,
    MessageCreate,
    RehabProgramAssignment,
)

logger = logging.getLogger(__name__)
_EMAIL_PATTERN = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


class DoctorService:
    def __init__(self, repository: SupabaseRepository, doctor_id: UUID) -> None:
        self.repository = repository
        self.doctor_id = doctor_id

    async def rows(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        result = await self.repository.rest("GET", table, params=params)
        return result if isinstance(result, list) else []

    async def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        result = await self.repository.rest(
            "POST", table, payload=values, prefer="return=representation"
        )
        if not isinstance(result, list) or not result:
            raise HTTPException(status_code=502, detail="The care service returned an incomplete response.")
        return result[0]

    async def patch(self, table: str, filters: dict[str, str], values: dict[str, Any]) -> dict[str, Any] | None:
        result = await self.repository.rest(
            "PATCH",
            table,
            params={**filters, "select": "*"},
            payload=values,
            prefer="return=representation",
        )
        return result[0] if isinstance(result, list) and result else None

    async def audit(
        self,
        actor_id: UUID,
        athlete_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        request_id: str | None = None,
    ) -> None:
        await self.repository.rest(
            "POST",
            "clinical_audit_logs",
            payload={
                "actor_id": str(actor_id),
                "athlete_id": str(athlete_id),
                "action": action,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
                "request_id": request_id,
            },
        )

    async def notification(
        self,
        *,
        recipient_id: UUID,
        actor_id: UUID | None,
        athlete_id: UUID | None,
        notification_type: str,
        title: str,
        body: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
    ) -> None:
        await self.repository.rest(
            "POST",
            "doctor_notifications",
            params={
                "on_conflict": "recipient_id,notification_type,resource_type,resource_id"
            },
            payload={
                "recipient_id": str(recipient_id),
                "actor_id": str(actor_id) if actor_id else None,
                "athlete_id": str(athlete_id) if athlete_id else None,
                "notification_type": notification_type,
                "title": title,
                "body": body,
                "resource_type": resource_type,
                "resource_id": str(resource_id) if resource_id else None,
            },
            prefer="resolution=merge-duplicates,return=minimal",
        )

    async def timeline(
        self,
        *,
        athlete_id: UUID,
        actor_id: UUID,
        actor_type: str,
        event_type: str,
        title: str,
        related_entity_type: str,
        entity_id: UUID,
    ) -> None:
        await self.repository.rest(
            "POST",
            "athlete_timeline_events",
            params={"on_conflict": "athlete_id,source_type,source_id"},
            payload={
                "athlete_id": str(athlete_id),
                "event_type": event_type,
                "source_type": "CLINICIAN_ENTERED" if actor_type == "DOCTOR" else actor_type,
                "source_id": str(uuid4()),
                "event_time": datetime.now(UTC).isoformat(),
                "title": title,
                "summary": "",
                "severity": None,
                "actor_type": actor_type,
                "actor_id": str(actor_id),
                "related_entity_type": related_entity_type,
                "related_entity_id": str(entity_id),
            },
            prefer="resolution=merge-duplicates,return=minimal",
        )

    async def require_relationship(self, athlete_id: UUID) -> dict[str, Any]:
        relationship = await self.rows(
            "doctor_athlete_relationships",
            {
                "doctor_id": f"eq.{self.doctor_id}",
                "athlete_id": f"eq.{athlete_id}",
                "status": "eq.ACTIVE",
                "select": "id,doctor_id,athlete_id,status,relationship_type,granted_at",
                "limit": "1",
            },
        )
        if not relationship:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Active athlete access is required.")
        return relationship[0]

    async def invite(self, body: InvitationCreate, *, request_id: str | None) -> dict[str, Any]:
        email = body.email.strip().lower()
        if not _EMAIL_PATTERN.fullmatch(email):
            raise HTTPException(status_code=422, detail="Enter a valid athlete email.")
        matched = await self.repository.rpc("lookup_athlete_by_email", {"p_email": email})
        if not matched:
            raise HTTPException(status_code=404, detail="No eligible athlete account matched that email.")
        athlete_id = UUID(str(matched))
        if athlete_id == self.doctor_id:
            raise HTTPException(status_code=422, detail="A doctor cannot invite their own account.")
        active = await self.rows(
            "doctor_athlete_relationships",
            {
                "doctor_id": f"eq.{self.doctor_id}",
                "athlete_id": f"eq.{athlete_id}",
                "status": "eq.ACTIVE",
                "select": "id",
                "limit": "1",
            },
        )
        if active:
            raise HTTPException(status_code=409, detail="This athlete is already connected to your account.")
        invitation = await self.insert(
            "doctor_athlete_invitations",
            {
                "doctor_id": str(self.doctor_id),
                "athlete_id": str(athlete_id),
                "email": email,
                "relationship_type": body.relationship_type,
                "message": body.message.strip(),
                "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
            },
        )
        invitation_id = UUID(invitation["id"])
        await self.notification(
            recipient_id=athlete_id,
            actor_id=self.doctor_id,
            athlete_id=athlete_id,
            notification_type="DOCTOR_INVITATION",
            title="Care team invitation",
            body="A clinician has invited you to connect on VitaPulse. Open VitaPulse to review and respond.",
            resource_type="INVITATION",
            resource_id=invitation_id,
        )
        await self.audit(
            self.doctor_id, athlete_id, "ATHLETE_INVITED", "INVITATION", invitation_id, request_id
        )
        return invitation

    async def list_athletes(
        self, *, query: str, offset: int, limit: int
    ) -> tuple[list[dict[str, Any]], int]:
        result = await self.repository.rpc(
            "search_connected_doctor_athletes",
            {
                "p_doctor_id": str(self.doctor_id),
                "p_query": query,
                "p_offset": offset,
                "p_limit": limit,
            },
        )
        if not isinstance(result, list):
            raise HTTPException(status_code=502, detail="The care service returned an invalid athlete directory.")
        return result, int(result[0]["total_count"]) if result else 0

    async def athlete_overview(self, athlete_id: UUID) -> dict[str, Any]:
        await self.require_relationship(athlete_id)
        profile_rows, athlete_rows, reports, sessions, readiness, recoveries, plans, tasks, insights = await asyncio.gather(
            self.rows("profiles", {"id": f"eq.{athlete_id}", "select": "id,display_name", "limit": "1"}),
            self.rows(
                "athlete_profiles",
                {"id": f"eq.{athlete_id}", "select": "id,sport,position,rehab_stage,injury_region", "limit": "1"},
            ),
            self.rows(
                "medical_reports",
                {"athlete_id": f"eq.{athlete_id}", "select": "id,report_date,uploaded_at,processing_status,analysis_status", "order": "uploaded_at.desc", "limit": "5"},
            ),
            self.rows(
                "rehab_sessions",
                {"athlete_id": f"eq.{athlete_id}", "select": "id,exercise_id,source,status,started_at,ended_at,completed_repetitions,movement_quality,fatigue_signal", "order": "started_at.desc", "limit": "5"},
            ),
            self.rows(
                "readiness_assessments",
                {"athlete_id": f"eq.{athlete_id}", "select": "id,status,recommendation,source,created_at", "order": "created_at.desc", "limit": "1"},
            ),
            self.rows(
                "recovery_records",
                {"athlete_id": f"eq.{athlete_id}", "select": "date,recovery_state,source,created_at", "order": "date.desc", "limit": "1"},
            ),
            self.rows(
                "care_plans",
                {"athlete_id": f"eq.{athlete_id}", "doctor_id": f"eq.{self.doctor_id}", "select": "id,title,status,rehab_stage,target_review_date,version,updated_at", "order": "updated_at.desc", "limit": "5"},
            ),
            self.rows(
                "review_tasks",
                {"athlete_id": f"eq.{athlete_id}", "doctor_id": f"eq.{self.doctor_id}", "select": "id,task_type,priority,title,status,due_at,created_at", "order": "created_at.desc", "limit": "10"},
            ),
            self.rows(
                "athlete_intelligence_insights",
                {"athlete_id": f"eq.{athlete_id}", "select": "id,period_start,period_end,insight_type,statement,source_ids,evidence_strength,status,interpretation_source,created_at", "order": "period_end.desc", "limit": "10"},
            ),
        )
        if not profile_rows or not athlete_rows:
            raise HTTPException(status_code=404, detail="Athlete profile was not found.")
        return {
            "profile": profile_rows[0],
            "athlete": athlete_rows[0],
            "medical_reports": reports,
            "rehab_sessions": sessions,
            "readiness": readiness[0] if readiness else None,
            "recovery": recoveries[0] if recoveries else None,
            "care_plans": plans,
            "review_tasks": tasks,
            "intelligence": insights,
            "safety": {"configured": False, "events": []},
            "last_updated": datetime.now(UTC).isoformat(),
        }

    async def records(self, athlete_id: UUID, domain: str, limit: int) -> dict[str, Any]:
        await self.require_relationship(athlete_id)
        domains: dict[str, tuple[tuple[str, str, str], ...]] = {
            "health": (
                ("medical_reports", "id,report_date,uploaded_at,processing_status,ocr_status,analysis_status,ocr_quality,pages_processed", "uploaded_at"),
                ("biomarker_measurements", "id,biomarker_name,canonical_name,value_numeric,value_text,unit,abnormal_flag,collection_date,source_type,source_page,confidence", "collection_date"),
                ("body_region_findings", "id,body_region_id,finding_type,severity,source_type,created_at", "created_at"),
                ("health_intelligence_items", "id,item_type,category,status,observed_at,created_at,source_ids", "created_at"),
                ("nutrition_entries", "id,entry_date,meal_type,calories,protein_g,carbohydrates_g,fat_g,fiber_g,hydration_ml,source", "entry_date"),
                ("medications", "id,name,status,start_date,end_date,source,created_at", "created_at"),
                ("anti_doping_reviews", "id,status,substance_name,reviewed_at,source_type", "created_at"),
                ("skin_screenings", "id,status,screening_date,source_type", "created_at"),
            ),
            "reports": (
                ("reports", "id,report_type,title,status,summary,ai_status,html_status,pdf_status,report_version,created_at,completed_at", "created_at"),
            ),
            "rehab": (
                ("rehab_programs", "id,name,status,stage,stage_order,created_at,updated_at", "updated_at"),
                ("rehab_program_exercises", "id,program_id,exercise_id,order_index,sets,repetitions,duration_seconds,rest_seconds,required,notes", "order_index"),
                ("rehab_sessions", "id,program_id,exercise_id,source,status,started_at,ended_at,sample_count,completed_repetitions,movement_quality,stability,smoothness,fatigue_signal,completion_rate", "started_at"),
                ("functional_test_results", "id,functional_test_id,session_id,duration_seconds,stability,movement_quality,source,result,created_at", "created_at"),
                ("readiness_assessments", "id,session_id,status,factors,recommendation,source,created_at", "created_at"),
                ("return_to_sport_assessments", "id,status,criteria_met,criteria_not_met,source,created_at", "created_at"),
            ),
            "movement": (
                ("movement_quality_results", "id,session_id,movement_quality,stability,smoothness,fatigue_signal,abnormal_events,source,calculation_version,created_at", "created_at"),
                ("movement_events", "id,session_id,timestamp,event_type,severity,description,source", "timestamp"),
                ("movement_metrics", "id,session_id,metric_name,metric_value,unit,source,calculation_version,created_at", "created_at"),
                ("movement_predictions", "id,session_id,prediction_type,prediction,model_name,model_version,feature_schema_version,timestamp,source", "timestamp"),
            ),
            "recovery": (
                ("sleep_records", "id,start_time,end_time,duration_minutes,quality_rating,interruptions,source,created_at", "end_time"),
                ("recovery_records", "id,date,recovery_state,supporting_factors,calculation_version,source,created_at", "date"),
                ("wellbeing_trends", "id,metric,period_start,period_end,classification,source_count,created_at", "period_end"),
            ),
            "wellbeing": (
                ("wellbeing_checkins", "id,energy,stress,fatigue,soreness,recovery_feeling,mood_self_report,source,created_at", "created_at"),
                ("camera_wellbeing_features", "id,session_id,face_presence_ratio,face_position_stability,head_movement_magnitude,head_movement_variability,head_orientation_range,capture_quality,feature_schema_version,source,created_at", "created_at"),
            ),
            "safety": (),
            "intelligence": (
                ("athlete_intelligence_snapshots", "id,report_id,period_start,period_end,data_completeness,calculation_version,summary_json,created_at", "period_end"),
                ("athlete_intelligence_insights", "id,snapshot_id,period_start,period_end,insight_type,statement,source_ids,evidence_strength,status,interpretation_source,created_at", "period_end"),
            ),
        }
        if domain not in domains:
            raise HTTPException(status_code=404, detail="The requested athlete workspace was not found.")
        if not domains[domain]:
            return {"domain": domain, "records": {}, "configured": False}
        results: dict[str, list[dict[str, Any]]] = {}
        for table, select, order in domains[domain]:
            results[table] = await self.rows(
                table,
                {
                    "athlete_id": f"eq.{athlete_id}",
                    "select": select,
                    "order": f"{order}.desc",
                    "limit": str(limit),
                },
            )
        return {"domain": domain, "records": results, "configured": True}

    async def create_plan(
        self, athlete_id: UUID, body: CarePlanCreate, request_id: str | None
    ) -> dict[str, Any]:
        await self.require_relationship(athlete_id)
        plan = await self.insert(
            "care_plans",
            {
                "athlete_id": str(athlete_id),
                "doctor_id": str(self.doctor_id),
                **body.model_dump(mode="json", exclude={"change_summary"}),
            },
        )
        await self.plan_version(plan, self.doctor_id, body.change_summary)
        await self.notification(
            recipient_id=athlete_id,
            actor_id=self.doctor_id,
            athlete_id=athlete_id,
            notification_type="CARE_PLAN_UPDATED",
            title="Care plan created",
            body="Your VitaPulse care plan was updated. Open VitaPulse to review the latest changes.",
            resource_type="CARE_PLAN",
            resource_id=UUID(plan["id"]),
        )
        await self.audit(self.doctor_id, athlete_id, "CARE_PLAN_CREATED", "CARE_PLAN", UUID(plan["id"]), request_id)
        await self.timeline(
            athlete_id=athlete_id,
            actor_id=self.doctor_id,
            actor_type="DOCTOR",
            event_type="CARE_PLAN_CREATED",
            title="Care plan created",
            related_entity_type="CARE_PLAN",
            entity_id=UUID(plan["id"]),
        )
        return plan

    async def plan_version(self, plan: dict[str, Any], actor_id: UUID, summary: str) -> None:
        goals, items = await asyncio.gather(
            self.rows(
                "care_plan_goals",
                {"care_plan_id": f"eq.{plan['id']}", "athlete_id": f"eq.{plan['athlete_id']}", "select": "*", "limit": "200"},
            ),
            self.rows(
                "care_plan_items",
                {"care_plan_id": f"eq.{plan['id']}", "athlete_id": f"eq.{plan['athlete_id']}", "select": "*", "limit": "200"},
            ),
        )
        await self.insert(
            "care_plan_versions",
            {
                "care_plan_id": plan["id"],
                "athlete_id": plan["athlete_id"],
                "version_number": plan["version"],
                "created_by": str(actor_id),
                "change_summary": summary,
                "snapshot": {"plan": plan, "goals": goals, "items": items},
            },
        )

    async def update_plan(
        self, athlete_id: UUID, plan_id: UUID, body: CarePlanUpdate, request_id: str | None
    ) -> dict[str, Any]:
        await self.require_relationship(athlete_id)
        plan = await self.rows(
            "care_plans",
            {"id": f"eq.{plan_id}", "athlete_id": f"eq.{athlete_id}", "doctor_id": f"eq.{self.doctor_id}", "select": "*", "limit": "1"},
        )
        if not plan:
            raise HTTPException(status_code=404, detail="Care plan was not found.")
        current = plan[0]
        values = body.model_dump(mode="json", exclude={"change_summary"}, exclude_unset=True)
        if not values:
            raise HTTPException(status_code=422, detail="At least one care plan change is required.")
        values["version"] = int(current["version"]) + 1
        updated = await self.patch(
            "care_plans",
            {
                "id": f"eq.{plan_id}", "athlete_id": f"eq.{athlete_id}",
                "doctor_id": f"eq.{self.doctor_id}", "version": f"eq.{current['version']}",
            },
            values,
        )
        if updated is None:
            raise HTTPException(status_code=409, detail="Care plan changed; reload and try again.")
        await self.plan_version(updated, self.doctor_id, body.change_summary)
        await self.notification(
            recipient_id=athlete_id, actor_id=self.doctor_id, athlete_id=athlete_id,
            notification_type="CARE_PLAN_UPDATED", title="Care plan updated",
            body="Your VitaPulse care plan was updated. Open VitaPulse to review the latest changes.",
            resource_type="CARE_PLAN", resource_id=plan_id,
        )
        await self.audit(self.doctor_id, athlete_id, "CARE_PLAN_UPDATED", "CARE_PLAN", plan_id, request_id)
        await self.timeline(
            athlete_id=athlete_id, actor_id=self.doctor_id, actor_type="DOCTOR",
            event_type="CARE_PLAN_UPDATED", title="Care plan updated",
            related_entity_type="CARE_PLAN", entity_id=plan_id,
        )
        return updated

    async def add_goal(self, athlete_id: UUID, plan_id: UUID, body: CareGoalCreate) -> dict[str, Any]:
        await self._owned_plan(athlete_id, plan_id)
        goal = await self.insert(
            "care_plan_goals",
            {"care_plan_id": str(plan_id), "athlete_id": str(athlete_id), **body.model_dump(mode="json")},
        )
        await self.bump_plan_version(athlete_id, plan_id, "Added a care plan goal.")
        await self.audit(self.doctor_id, athlete_id, "CARE_PLAN_GOAL_ADDED", "CARE_PLAN_GOAL", UUID(goal["id"]))
        return goal

    async def add_item(
        self, athlete_id: UUID, plan_id: UUID, body: CareItemCreate, request_id: str | None
    ) -> dict[str, Any]:
        await self._owned_plan(athlete_id, plan_id)
        if body.item_type in {"EXERCISE", "PROGRAM", "FUNCTIONAL_TEST"} and body.linked_entity is None:
            raise HTTPException(status_code=422, detail="Select an existing exercise, program, or functional test.")
        linked_tables = {
            "EXERCISE": ("rehab_exercises", {"active": "eq.true"}),
            "PROGRAM": ("rehab_programs", {"athlete_id": f"eq.{athlete_id}"}),
            "FUNCTIONAL_TEST": ("functional_tests", {"active": "eq.true"}),
        }
        rehab_program_id: str | None = None
        if body.item_type in linked_tables:
            table, extra_filters = linked_tables[body.item_type]
            linked = await self.rows(
                table,
                {
                    "id": f"eq.{body.linked_entity}",
                    "select": "id,athlete_id" if body.item_type == "PROGRAM" else "id",
                    "limit": "1",
                    **extra_filters,
                },
            )
            if not linked:
                raise HTTPException(status_code=404, detail="The selected rehabilitation item was not found.")
            if body.item_type == "PROGRAM":
                rehab_program_id = linked[0]["id"]
        if body.item_type == "EXERCISE":
            plan = await self._owned_plan(athlete_id, plan_id)
            program = await self.insert(
                "rehab_programs",
                {
                    "athlete_id": str(athlete_id),
                    "name": body.title,
                    "description": body.description,
                    "goal": body.instructions,
                    "stage": plan.get("rehab_stage"),
                    "start_date": body.start_date.isoformat() if body.start_date else None,
                    "target_end_date": body.end_date.isoformat() if body.end_date else None,
                    "assigned_by": str(self.doctor_id),
                    "source": "CLINICIAN_ASSIGNED",
                    "status": "ACTIVE",
                },
            )
            rehab_program_id = program["id"]
            await self.repository.rest(
                "POST",
                "rehab_program_exercises",
                payload={
                    "athlete_id": str(athlete_id),
                    "program_id": rehab_program_id,
                    "exercise_id": str(body.linked_entity),
                    "order_index": 0,
                    "sets": body.sets or 1,
                    "repetitions": body.repetitions,
                    "duration_seconds": body.duration_seconds,
                    "rest_seconds": body.rest_seconds if body.rest_seconds is not None else 30,
                    "required": True,
                    "notes": body.instructions or body.description,
                    "source": "CLINICIAN_ASSIGNED",
                },
            )
        item = await self.insert(
            "care_plan_items",
            {
                "care_plan_id": str(plan_id),
                "athlete_id": str(athlete_id),
                "assigned_by": str(self.doctor_id),
                "rehab_program_id": rehab_program_id,
                **body.model_dump(mode="json"),
            },
        )
        await self.bump_plan_version(athlete_id, plan_id, "Added a care plan assignment.")
        await self.notification(
            recipient_id=athlete_id, actor_id=self.doctor_id, athlete_id=athlete_id,
            notification_type="EXERCISE_ASSIGNED" if body.item_type == "EXERCISE" else "CARE_PLAN_UPDATED",
            title="Care plan assignment",
            body="A new item was added to your VitaPulse care plan. Open VitaPulse to review it.",
            resource_type="CARE_PLAN_ITEM", resource_id=UUID(item["id"]),
        )
        await self.audit(self.doctor_id, athlete_id, "CARE_PLAN_ITEM_ASSIGNED", "CARE_PLAN_ITEM", UUID(item["id"]), request_id)
        await self.timeline(
            athlete_id=athlete_id, actor_id=self.doctor_id, actor_type="DOCTOR",
            event_type="EXERCISE_ASSIGNED" if body.item_type == "EXERCISE" else "CARE_PLAN_ITEM_ASSIGNED",
            title="Care plan assignment added", related_entity_type="CARE_PLAN_ITEM", entity_id=UUID(item["id"]),
        )
        return item

    async def assign_program(
        self,
        athlete_id: UUID,
        plan_id: UUID,
        body: RehabProgramAssignment,
        request_id: str | None,
    ) -> dict[str, Any]:
        plan = await self._owned_plan(athlete_id, plan_id)
        if body.target_end_date and body.start_date and body.target_end_date < body.start_date:
            raise HTTPException(status_code=422, detail="Program end date must follow its start date.")
        exercise_ids = list(dict.fromkeys(str(item.exercise_id) for item in body.exercises))
        exercises = await self.rows(
            "rehab_exercises",
            {"id": f"in.({','.join(exercise_ids)})", "active": "eq.true", "select": "id", "limit": "100"},
        )
        if {row["id"] for row in exercises} != set(exercise_ids):
            raise HTTPException(status_code=422, detail="Choose active exercises from the VitaPulse exercise library.")
        program = await self.insert(
            "rehab_programs",
            {
                "athlete_id": str(athlete_id),
                "name": body.name,
                "description": body.description,
                "goal": body.goal,
                "stage": body.stage or plan.get("rehab_stage"),
                "start_date": body.start_date.isoformat() if body.start_date else None,
                "target_end_date": body.target_end_date.isoformat() if body.target_end_date else None,
                "assigned_by": str(self.doctor_id),
                "source": "CLINICIAN_ASSIGNED",
                "status": "ACTIVE",
            },
        )
        assignments = [
            {
                "athlete_id": str(athlete_id),
                "program_id": program["id"],
                "exercise_id": str(item.exercise_id),
                "order_index": index,
                "sets": item.sets,
                "repetitions": item.repetitions,
                "duration_seconds": item.duration_seconds,
                "rest_seconds": item.rest_seconds,
                "required": item.required,
                "notes": item.notes,
                "source": "CLINICIAN_ASSIGNED",
            }
            for index, item in enumerate(body.exercises)
        ]
        await self.repository.rest("POST", "rehab_program_exercises", payload=assignments)
        care_item = await self.insert(
            "care_plan_items",
            {
                "care_plan_id": str(plan_id),
                "athlete_id": str(athlete_id),
                "assigned_by": str(self.doctor_id),
                "item_type": "PROGRAM",
                "title": body.name,
                "description": body.description,
                "linked_entity": program["id"],
                "rehab_program_id": program["id"],
                "instructions": body.goal,
                "start_date": body.start_date.isoformat() if body.start_date else None,
                "end_date": body.target_end_date.isoformat() if body.target_end_date else None,
            },
        )
        await self.bump_plan_version(athlete_id, plan_id, "Assigned a rehabilitation program.")
        await self.notification(
            recipient_id=athlete_id, actor_id=self.doctor_id, athlete_id=athlete_id,
            notification_type="EXERCISE_ASSIGNED", title="Rehabilitation program assigned",
            body="A rehabilitation program was added to your VitaPulse plan. Open VitaPulse to review it.",
            resource_type="REHAB_PROGRAM", resource_id=UUID(program["id"]),
        )
        await self.audit(self.doctor_id, athlete_id, "REHAB_PROGRAM_ASSIGNED", "REHAB_PROGRAM", UUID(program["id"]), request_id)
        await self.timeline(
            athlete_id=athlete_id, actor_id=self.doctor_id, actor_type="DOCTOR",
            event_type="REHAB_PROGRAM_ASSIGNED", title="Rehabilitation program assigned",
            related_entity_type="REHAB_PROGRAM", entity_id=UUID(program["id"]),
        )
        return {"program": program, "care_plan_item": care_item}

    async def bump_plan_version(
        self, athlete_id: UUID, plan_id: UUID, change_summary: str
    ) -> dict[str, Any]:
        current = await self._owned_plan(athlete_id, plan_id)
        updated = await self.patch(
            "care_plans",
            {
                "id": f"eq.{plan_id}",
                "athlete_id": f"eq.{athlete_id}",
                "doctor_id": f"eq.{self.doctor_id}",
                "version": f"eq.{current['version']}",
            },
            {"version": int(current["version"]) + 1},
        )
        if updated is None:
            raise HTTPException(status_code=409, detail="Care plan changed; reload and try again.")
        await self.plan_version(updated, self.doctor_id, change_summary)
        await self.notification(
            recipient_id=athlete_id, actor_id=self.doctor_id, athlete_id=athlete_id,
            notification_type="CARE_PLAN_UPDATED", title="Care plan updated",
            body="Your VitaPulse care plan was updated. Open VitaPulse to review the latest changes.",
            resource_type="CARE_PLAN", resource_id=plan_id,
        )
        return updated

    async def _owned_plan(self, athlete_id: UUID, plan_id: UUID) -> dict[str, Any]:
        await self.require_relationship(athlete_id)
        plans = await self.rows(
            "care_plans",
            {"id": f"eq.{plan_id}", "athlete_id": f"eq.{athlete_id}", "doctor_id": f"eq.{self.doctor_id}", "select": "*", "limit": "1"},
        )
        if not plans:
            raise HTTPException(status_code=404, detail="Care plan was not found.")
        return plans[0]

    async def create_note(
        self, athlete_id: UUID, body: DoctorNoteCreate, request_id: str | None
    ) -> dict[str, Any]:
        await self.require_relationship(athlete_id)
        note = await self.insert(
            "doctor_notes",
            {"athlete_id": str(athlete_id), "doctor_id": str(self.doctor_id), **body.model_dump()},
        )
        await self.insert(
            "doctor_note_versions",
            {
                "note_id": note["id"], "athlete_id": str(athlete_id), "doctor_id": str(self.doctor_id),
                "version_number": 1, "title": note["title"], "content": note["content"],
                "visibility": note["visibility"], "edit_reason": "Note created.",
            },
        )
        await self.audit(self.doctor_id, athlete_id, "DOCTOR_NOTE_CREATED", "DOCTOR_NOTE", UUID(note["id"]), request_id)
        if body.visibility == "ATHLETE_VISIBLE":
            await self.notification(
                recipient_id=athlete_id, actor_id=self.doctor_id, athlete_id=athlete_id,
                notification_type="DOCTOR_NOTE_SHARED", title="Doctor update",
                body="Your care team shared an update. Open VitaPulse to review it.",
                resource_type="DOCTOR_NOTE", resource_id=UUID(note["id"]),
            )
        return note

    async def update_note(
        self, athlete_id: UUID, note_id: UUID, body: DoctorNoteUpdate, request_id: str | None
    ) -> dict[str, Any]:
        await self.require_relationship(athlete_id)
        notes = await self.rows(
            "doctor_notes",
            {"id": f"eq.{note_id}", "athlete_id": f"eq.{athlete_id}", "doctor_id": f"eq.{self.doctor_id}", "select": "*", "limit": "1"},
        )
        if not notes:
            raise HTTPException(status_code=404, detail="Doctor note was not found.")
        current = notes[0]
        version = int(current["version"]) + 1
        updated = await self.patch(
            "doctor_notes",
            {
                "id": f"eq.{note_id}", "athlete_id": f"eq.{athlete_id}",
                "doctor_id": f"eq.{self.doctor_id}", "version": f"eq.{current['version']}",
            },
            {**body.model_dump(exclude={"edit_reason"}), "version": version},
        )
        if updated is None:
            raise HTTPException(status_code=409, detail="The note changed; reload and try again.")
        await self.insert(
            "doctor_note_versions",
            {
                "note_id": str(note_id), "athlete_id": str(athlete_id), "doctor_id": str(self.doctor_id),
                "version_number": version, "title": updated["title"], "content": updated["content"],
                "visibility": updated["visibility"], "edit_reason": body.edit_reason,
            },
        )
        await self.audit(self.doctor_id, athlete_id, "DOCTOR_NOTE_UPDATED", "DOCTOR_NOTE", note_id, request_id)
        if updated["visibility"] == "ATHLETE_VISIBLE":
            await self.notification(
                recipient_id=athlete_id, actor_id=self.doctor_id, athlete_id=athlete_id,
                notification_type="DOCTOR_NOTE_SHARED", title="Doctor update",
                body="Your care team shared an update. Open VitaPulse to review it.",
                resource_type="DOCTOR_NOTE", resource_id=note_id,
            )
        return updated

    async def create_review(
        self, athlete_id: UUID, body: DoctorReviewCreate, request_id: str | None
    ) -> dict[str, Any]:
        await self.require_relationship(athlete_id)
        review = await self.insert(
            "doctor_reviews",
            {"athlete_id": str(athlete_id), "doctor_id": str(self.doctor_id), **body.model_dump(mode="json")},
        )
        await self.audit(self.doctor_id, athlete_id, "DOCTOR_REVIEW_CREATED", "DOCTOR_REVIEW", UUID(review["id"]), request_id)
        await self.timeline(
            athlete_id=athlete_id, actor_id=self.doctor_id, actor_type="DOCTOR",
            event_type="DOCTOR_REVIEW_CREATED", title="Clinician review recorded",
            related_entity_type="DOCTOR_REVIEW", entity_id=UUID(review["id"]),
        )
        if body.next_review_date:
            await self.create_task(
                athlete_id=athlete_id,
                task_type="REVIEW_FOLLOW_UP",
                priority="MEDIUM",
                subject_type="DOCTOR_REVIEW",
                subject_id=UUID(review["id"]),
                title="Review athlete follow-up",
                description="A clinician follow-up review is scheduled.",
                due_at=datetime.combine(body.next_review_date, datetime.min.time(), UTC),
            )
        return review

    async def create_task(
        self,
        *,
        athlete_id: UUID,
        task_type: str,
        priority: str,
        subject_type: str,
        subject_id: UUID,
        title: str,
        description: str = "",
        due_at: datetime | None = None,
    ) -> None:
        await self.repository.rest(
            "POST",
            "review_tasks",
            params={"on_conflict": "doctor_id,task_type,subject_type,subject_id"},
            payload={
                "doctor_id": str(self.doctor_id), "athlete_id": str(athlete_id), "task_type": task_type,
                "priority": priority, "subject_type": subject_type, "subject_id": str(subject_id),
                "title": title, "description": description, "due_at": due_at.isoformat() if due_at else None,
            },
            prefer="resolution=merge-duplicates,return=minimal",
        )
        await self.notification(
            recipient_id=self.doctor_id, actor_id=None, athlete_id=athlete_id,
            notification_type="REVIEW_TASK", title="Review task available",
            body="A care-loop item is ready for clinician review.",
            resource_type=subject_type, resource_id=subject_id,
        )

    async def send_message(
        self, athlete_id: UUID, body: MessageCreate, request_id: str | None
    ) -> dict[str, Any]:
        await self.require_relationship(athlete_id)
        threads = await self.rows(
            "message_threads",
            {"doctor_id": f"eq.{self.doctor_id}", "athlete_id": f"eq.{athlete_id}", "select": "id", "limit": "1"},
        )
        thread = threads[0] if threads else await self.insert(
            "message_threads", {"doctor_id": str(self.doctor_id), "athlete_id": str(athlete_id)}
        )
        message = await self.insert(
            "messages",
            {
                "thread_id": thread["id"], "athlete_id": str(athlete_id),
                "sender_id": str(self.doctor_id), **body.model_dump(),
            },
        )
        await self.patch(
            "message_threads", {"id": f"eq.{thread['id']}", "doctor_id": f"eq.{self.doctor_id}"},
            {"updated_at": datetime.now(UTC).isoformat()},
        )
        await self.notification(
            recipient_id=athlete_id, actor_id=self.doctor_id, athlete_id=athlete_id,
            notification_type="ATHLETE_MESSAGE", title="Care team message",
            body="You have a new VitaPulse care-team message. Open VitaPulse to read it.",
            resource_type="MESSAGE", resource_id=UUID(message["id"]),
        )
        await self.audit(self.doctor_id, athlete_id, "CARE_MESSAGE_SENT", "MESSAGE", UUID(message["id"]), request_id)
        return {"thread": thread, "message": message}


class CareLoopService:
    def __init__(self, repository: SupabaseRepository) -> None:
        self.repository = repository

    async def rehab_completed(
        self, athlete_id: UUID, actor_id: UUID, session: dict[str, Any], request_id: str | None = None
    ) -> None:
        doctors = await self.repository.rest(
            "GET",
            "doctor_athlete_relationships",
            params={
                "athlete_id": f"eq.{athlete_id}", "status": "eq.ACTIVE",
                "select": "doctor_id", "limit": "100",
            },
        )
        if not isinstance(doctors, list):
            raise HTTPException(status_code=502, detail="Care-team review tasks could not be synchronized.")
        needs_review = session.get("movement_quality") == "NEEDS_ATTENTION" or session.get("fatigue_signal") == "HIGH"
        for row in doctors:
            doctor_id = UUID(row["doctor_id"])
            service = DoctorService(self.repository, doctor_id)
            if needs_review:
                await service.create_task(
                    athlete_id=athlete_id,
                    task_type="REHAB_SESSION_REVIEW",
                    priority="HIGH" if session.get("fatigue_signal") == "HIGH" else "MEDIUM",
                    subject_type="REHAB_SESSION",
                    subject_id=UUID(session["id"]),
                    title="Review completed rehabilitation session",
                    description="Session results include a movement or fatigue signal for review.",
                )
            await service.notification(
                recipient_id=doctor_id, actor_id=actor_id, athlete_id=athlete_id,
                notification_type="REHAB_SESSION_COMPLETED", title="Athlete progress updated",
                body="A connected athlete completed a rehabilitation session. Open VitaPulse to review progress.",
                resource_type="REHAB_SESSION", resource_id=UUID(session["id"]),
            )
        await self.repository.rest(
            "POST",
            "athlete_timeline_events",
            payload={
                "athlete_id": str(athlete_id),
                "event_type": "REHAB_SESSION_COMPLETED",
                "source_type": session.get("source", "ATHLETE_REPORTED"),
                "source_id": str(session["id"]),
                "event_time": session.get("ended_at") or datetime.now(UTC).isoformat(),
                "title": "Rehabilitation session completed",
                "summary": "",
                "severity": None,
                "actor_type": "ATHLETE",
                "actor_id": str(actor_id),
                "related_entity_type": "REHAB_SESSION",
                "related_entity_id": str(session["id"]),
            },
            prefer="resolution=merge-duplicates,return=minimal",
        )
        logger.info(
            "care_loop_rehab_completed",
            extra={"request_id": request_id or "-", "athlete_id": str(athlete_id), "session_id": session["id"]},
        )
