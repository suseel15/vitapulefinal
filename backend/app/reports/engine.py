import hashlib
import json
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.ai.gemini_provider import AIProviderUnavailable, GeminiBlockedResponse, GeminiProvider
from app.ai.prompts import PROMPT_VERSION, SCHEMA_VERSION, GLOBAL_SYSTEM_PROMPT, feature_prompt
from app.ai.safety import AIReportSafetyValidator, AIValidationError
from app.core.config import Settings
from app.repositories.health_repository import HealthRepository
from app.repositories.supabase import SupabaseRepository
from app.reports.builders.collector import collect_report_sources
from app.reports.email_delivery import EmailDeliveryUnavailable, send_report_email
from app.reports.longitudinal import build_longitudinal_insights
from app.reports.renderers import render_html, render_pdf
from app.reports.schemas import (
    AIInterpretation,
    DataCompleteness,
    LongitudinalInsight,
    ReportData,
    ReportSection,
    ReportRequest,
    ReportSource,
    ReportStatus,
    ReportType,
)
from app.services.contracts import AIProvider, AIRequest

logger = logging.getLogger(__name__)
_SAFE_ENUM = re.compile(r"^[A-Z][A-Z0-9_ -]{0,63}$")
_REPORT_TITLES = {
    report_type: report_type.value.replace("_", " ").title() for report_type in ReportType
}


class ReportEngine:
    def __init__(
        self,
        settings: Settings,
        repository: SupabaseRepository,
        *,
        ai_provider: AIProvider | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.ai_provider = ai_provider or GeminiProvider(settings)

    async def create(
        self,
        *,
        athlete_id: UUID,
        requested_by: UUID,
        request: ReportRequest,
    ) -> tuple[UUID, bool]:
        if not self.settings.reports_enabled:
            raise RuntimeError("Report generation is disabled.")
        if request.include_pdf and not self.settings.pdf_generation_enabled:
            raise RuntimeError("PDF report generation is disabled.")
        if request.idempotency_key:
            existing = await self._rows(
                "reports",
                {
                    "athlete_id": f"eq.{athlete_id}",
                    "idempotency_key": f"eq.{request.idempotency_key}",
                    "select": "id",
                    "limit": "1",
                },
            )
            if existing:
                return UUID(existing[0]["id"]), False

        report_id = uuid4()
        await self._insert(
            "reports",
            {
                "id": str(report_id),
                "athlete_id": str(athlete_id),
                "created_by": str(requested_by),
                "report_type": request.report_type.value,
                "feature_id": str(request.feature_id) if request.feature_id else None,
                "status": ReportStatus.QUEUED.value,
                "title": _REPORT_TITLES[request.report_type],
                "date_range_start": request.date_range_start.isoformat() if request.date_range_start else None,
                "date_range_end": request.date_range_end.isoformat() if request.date_range_end else None,
                "schema_version": SCHEMA_VERSION,
                "report_version": self.settings.report_default_template_version,
                "template_version": self.settings.report_default_template_version,
                "idempotency_key": request.idempotency_key,
                "report_data": {},
            },
        )
        await self._insert(
            "report_jobs",
            {
                "athlete_id": str(athlete_id),
                "report_id": str(report_id),
                "job_type": "REPORT_GENERATION",
                "status": "QUEUED",
            },
        )
        await self._event(athlete_id, report_id, "QUEUED", "COMPLETED")
        if request.include_email and request.recipient:
            await self._insert(
                "report_email_deliveries",
                {
                    "athlete_id": str(athlete_id),
                    "report_id": str(report_id),
                    "recipient": request.recipient,
                    "status": "QUEUED",
                },
            )
            await self._patch_report(athlete_id, report_id, {"email_status": "QUEUED"})
        return report_id, True

    async def process(
        self,
        *,
        athlete_id: UUID,
        requested_by: UUID,
        report_id: UUID,
        request: ReportRequest,
    ) -> None:
        started = time.monotonic()
        try:
            await self._job_status(athlete_id, report_id, "RUNNING")
            await self._stage(athlete_id, report_id, ReportStatus.COLLECTING_DATA)
            effective_request = _with_default_period(request)
            current_sources, sections, category_summaries, gaps, completeness = await collect_report_sources(
                HealthRepository(self.repository, athlete_id),
                effective_request,
            )
            prior_sources: list[ReportSource] = []
            longitudinal: list[LongitudinalInsight] = []
            calculated_sources: list[ReportSource] = []
            longitudinal_limitations: list[str] = []
            if _uses_longitudinal_data(request.report_type):
                if not self.settings.athlete_intelligence_enabled:
                    longitudinal_limitations.append(
                        "Longitudinal intelligence is disabled by configuration; no period comparison was generated."
                    )
                else:
                    prior_request = _previous_period(effective_request)
                    if prior_request is not None:
                        prior_sources, _, _, _, _ = await collect_report_sources(
                            HealthRepository(self.repository, athlete_id),
                            prior_request,
                        )
                    if prior_sources:
                        current_sources, prior_sources, sections = _renumber_sources(
                            current_sources,
                            prior_sources,
                            sections,
                        )
                        calculated_sources, longitudinal, longitudinal_limitations = build_longitudinal_insights(
                            current_sources,
                            prior_sources,
                            current_period_end=effective_request.date_range_end or datetime.now(UTC),
                        )
                    else:
                        current_sources, _, sections = _renumber_sources(current_sources, [], sections)
                        longitudinal_limitations.append(
                            "No records were available in the comparison period; no longitudinal comparison was generated."
                        )
                    gaps.extend(longitudinal_limitations)
            source_list = [*current_sources, *prior_sources, *calculated_sources]
            now = datetime.now(UTC)
            report_data = ReportData(
                report_id=report_id,
                athlete_id=athlete_id,
                requested_by=requested_by,
                report_type=request.report_type,
                title=_REPORT_TITLES[request.report_type],
                generated_at=now,
                date_range_start=effective_request.date_range_start,
                date_range_end=effective_request.date_range_end,
                sections=sections,
                sources=source_list,
                longitudinal_insights=longitudinal,
                source_categories=category_summaries,
                data_completeness=completeness,
                data_gaps=gaps,
                factual_summary=(
                    f"Found {len(source_list)} source records across "
                    f"{sum(1 for category in category_summaries if category.source_count)} categories; "
                    f"generated {len(longitudinal)} deterministic longitudinal comparisons."
                ),
                limitations=[
                    "This report includes only records available in the connected VitaPulse data sources.",
                    "Absence of a record does not establish absence of a health or performance condition.",
                    *longitudinal_limitations,
                ],
                report_version=self.settings.report_default_template_version,
                template_version=self.settings.report_default_template_version,
            )
            input_hash = _sha256(_canonical_json([source.model_dump(mode="json") for source in source_list]))
            await self._save_sources(athlete_id, report_id, source_list)
            if _uses_longitudinal_data(request.report_type) and self.settings.athlete_intelligence_enabled:
                await self._save_intelligence_snapshot(report_data)
            await self._stage(athlete_id, report_id, ReportStatus.VALIDATING_INPUT)
            await self._register_versions(request.report_type)

            if request.include_ai and source_list:
                await self._stage(athlete_id, report_id, ReportStatus.GENERATING_AI)
                ai_started = time.monotonic()
                try:
                    generated = await self.ai_provider.generate(
                        AIRequest(
                            task=feature_prompt(request.report_type),
                            structured_input=_ai_safe_input(source_list),
                        )
                    )
                    await self._stage(athlete_id, report_id, ReportStatus.VALIDATING_AI)
                    interpreted = AIReportSafetyValidator().validate(
                        AIInterpretation.model_validate(generated.content),
                        source_list,
                    )
                except (AIProviderUnavailable, GeminiBlockedResponse):
                    report_data.ai_status = "UNAVAILABLE"
                    await self._set_ai_status(athlete_id, report_id, "UNAVAILABLE")
                except (AIValidationError, ValidationError):
                    report_data.ai_status = "REJECTED"
                    await self._set_ai_status(athlete_id, report_id, "REJECTED")
                    await self._event(athlete_id, report_id, "AI_VALIDATION", "REJECTED")
                else:
                    report_data.ai_interpretation = interpreted
                    report_data.ai_status = "COMPLETED"
                    await self._save_ai_output(
                        athlete_id,
                        report_id,
                        generated.provider,
                        interpreted,
                        input_hash,
                        round((time.monotonic() - ai_started) * 1000),
                    )
                    await self._set_ai_status(athlete_id, report_id, "COMPLETED")
            else:
                report_data.ai_status = "SKIPPED"
                await self._set_ai_status(athlete_id, report_id, "SKIPPED")

            report_json = report_data.model_dump(mode="json")
            await self._patch_report(
                athlete_id,
                report_id,
                {
                    "input_hash": input_hash,
                    "report_data": report_json,
                    "date_range_start": report_json["date_range_start"],
                    "date_range_end": report_json["date_range_end"],
                    "prompt_version": PROMPT_VERSION,
                    "schema_version": SCHEMA_VERSION,
                    "template_version": report_data.template_version,
                    "source_version": "source-v1",
                    "summary": report_data.factual_summary,
                    "ai_status": report_data.ai_status,
                    "provider": self.settings.ai_provider if report_data.ai_status == "COMPLETED" else None,
                    "model": self.settings.gemini_model if report_data.ai_status == "COMPLETED" else None,
                },
            )
            await self._stage(athlete_id, report_id, ReportStatus.BUILDING_REPORT)
            html_content = render_html(report_data)
            await self._stage(athlete_id, report_id, ReportStatus.RENDERING_HTML)
            await self._store_file(
                athlete_id, report_id, "HTML", "text/html; charset=utf-8", html_content
            )
            if request.include_pdf:
                await self._stage(athlete_id, report_id, ReportStatus.RENDERING_PDF)
                pdf_content = render_pdf(report_data)
                await self._store_file(athlete_id, report_id, "PDF", "application/pdf", pdf_content)
                await self._set_file_status(athlete_id, report_id, "pdf_status", "COMPLETED")
            else:
                await self._set_file_status(athlete_id, report_id, "pdf_status", "SKIPPED")
            await self._set_file_status(athlete_id, report_id, "html_status", "COMPLETED")
            await self._stage(athlete_id, report_id, ReportStatus.COMPLETED)
            await self._patch_report(
                athlete_id,
                report_id,
                {"status": ReportStatus.COMPLETED.value, "completed_at": now.isoformat()},
            )
            await self._job_status(athlete_id, report_id, "COMPLETED")
            await self._event(athlete_id, report_id, "COMPLETED", "COMPLETED")
            try:
                await self._deliver_queued_emails(athlete_id, requested_by, report_id)
            except (EmailDeliveryUnavailable, HTTPException, KeyError, ValueError):
                logger.warning("report_email_delivery_failed", extra={"report_id": str(report_id)})
            logger.info("report_generation_completed", extra={"report_id": str(report_id), "elapsed_ms": round((time.monotonic() - started) * 1000)})
        except Exception:
            logger.exception("report_generation_failed", extra={"report_id": str(report_id)})
            await self._patch_report(
                athlete_id,
                report_id,
                {"status": ReportStatus.FAILED.value, "error_code": "REPORT_GENERATION_FAILED"},
            )
            await self._job_status(athlete_id, report_id, "FAILED", error_code="REPORT_GENERATION_FAILED")
            await self._event(athlete_id, report_id, "FAILED", "FAILED", "REPORT_GENERATION_FAILED")
            raise

    async def queue_email(
        self,
        *,
        athlete_id: UUID,
        requested_by: UUID,
        report_id: UUID,
        recipient: str,
    ) -> UUID:
        report = await self._report(athlete_id, report_id)
        if report.get("status") != ReportStatus.COMPLETED.value:
            raise ValueError("Only completed reports can be emailed.")
        delivery = await self._insert(
            "report_email_deliveries",
            {
                "athlete_id": str(athlete_id),
                "report_id": str(report_id),
                "recipient": recipient,
                "status": "QUEUED",
            },
        )
        delivery_id = UUID(delivery["id"])
        await self._insert(
            "report_jobs",
            {
                "athlete_id": str(athlete_id),
                "report_id": str(report_id),
                "job_type": "EMAIL",
                "status": "QUEUED",
            },
        )
        return delivery_id

    async def process_email(
        self,
        *,
        athlete_id: UUID,
        requested_by: UUID,
        report_id: UUID,
        delivery_id: UUID,
        recipient: str,
    ) -> None:
        await self._job_status(athlete_id, report_id, "RUNNING", job_type="EMAIL")
        await self._deliver_email(athlete_id, requested_by, report_id, delivery_id, recipient)

    async def _deliver_queued_emails(
        self,
        athlete_id: UUID,
        requested_by: UUID,
        report_id: UUID,
    ) -> None:
        queued = await self._rows(
            "report_email_deliveries",
            {
                "athlete_id": f"eq.{athlete_id}",
                "report_id": f"eq.{report_id}",
                "status": "eq.QUEUED",
                "select": "id,recipient",
                "limit": "10",
            },
        )
        for delivery in queued:
            await self._deliver_email(
                athlete_id,
                requested_by,
                report_id,
                UUID(delivery["id"]),
                delivery["recipient"],
            )

    async def _deliver_email(
        self,
        athlete_id: UUID,
        requested_by: UUID,
        report_id: UUID,
        delivery_id: UUID,
        recipient: str,
    ) -> None:
        await self._patch(
            "report_email_deliveries",
            {"id": f"eq.{delivery_id}", "athlete_id": f"eq.{athlete_id}"},
            {"status": "SENDING"},
        )
        await self._patch_report(athlete_id, report_id, {"email_status": "SENDING"})
        await self._event(athlete_id, report_id, "EMAIL", "PROCESSING")
        try:
            file_rows = await self._rows(
                "report_files",
                {
                    "athlete_id": f"eq.{athlete_id}",
                    "report_id": f"eq.{report_id}",
                    "file_type": "eq.PDF",
                    "select": "storage_bucket,storage_path",
                    "limit": "1",
                },
            )
            if not file_rows:
                raise EmailDeliveryUnavailable("No PDF report is available for delivery.")
            signed_url = await self.repository.signed_url(
                file_rows[0]["storage_bucket"],
                file_rows[0]["storage_path"],
                self.settings.report_signed_url_expiry_seconds,
            )
            report = await self._report(athlete_id, report_id)
            await send_report_email(
                self.settings,
                recipient=recipient,
                title=report["title"],
                report_url=signed_url,
                expires_in_seconds=self.settings.report_signed_url_expiry_seconds,
            )
        except (EmailDeliveryUnavailable, HTTPException, KeyError, ValueError):
            await self._patch(
                "report_email_deliveries",
                {"id": f"eq.{delivery_id}", "athlete_id": f"eq.{athlete_id}"},
                {"status": "FAILED", "error_code": "EMAIL_DELIVERY_FAILED", "completed_at": datetime.now(UTC).isoformat()},
            )
            await self._patch_report(athlete_id, report_id, {"email_status": "FAILED"})
            await self._event(athlete_id, report_id, "EMAIL", "FAILED", "EMAIL_DELIVERY_FAILED")
            await self._job_status(athlete_id, report_id, "FAILED", job_type="EMAIL", error_code="EMAIL_DELIVERY_FAILED")
            raise
        await self._patch(
            "report_email_deliveries",
            {"id": f"eq.{delivery_id}", "athlete_id": f"eq.{athlete_id}"},
            {"status": "SENT", "completed_at": datetime.now(UTC).isoformat()},
        )
        await self._patch_report(athlete_id, report_id, {"email_status": "SENT"})
        await self._patch_latest_job(athlete_id, report_id, "EMAIL", "COMPLETED")
        await self._event(athlete_id, report_id, "EMAIL", "COMPLETED")
        await self._audit(athlete_id, requested_by, report_id, "REPORT_EMAILED")

    async def _store_file(
        self,
        athlete_id: UUID,
        report_id: UUID,
        file_type: str,
        mime_type: str,
        content: bytes,
    ) -> None:
        if not content or len(content) > 52_428_800:
            raise ValueError("Generated report file exceeded storage limits.")
        extension = "html" if file_type == "HTML" else "pdf"
        object_path = f"{athlete_id}/{report_id}/{file_type.lower()}-v{self.settings.report_default_template_version}.{extension}"
        await self._stage(athlete_id, report_id, ReportStatus.UPLOADING)
        await self.repository.upload_object(
            self.settings.report_storage_bucket,
            object_path,
            content,
            mime_type,
            upsert=True,
        )
        await self._upsert(
            "report_files",
            {
                "athlete_id": str(athlete_id),
                "report_id": str(report_id),
                "file_type": file_type,
                "storage_bucket": self.settings.report_storage_bucket,
                "storage_path": object_path,
                "mime_type": mime_type,
                "file_size": len(content),
                "sha256": _sha256(content),
            },
            "report_id,file_type",
        )

    async def _save_sources(self, athlete_id: UUID, report_id: UUID, sources: list[Any]) -> None:
        for source in sources:
            timeline_title = source.source_label.removeprefix("Previous period · ")
            await self._upsert(
                "report_sources",
                {
                    "athlete_id": str(athlete_id),
                    "report_id": str(report_id),
                    "source_type": source.source_type.value,
                    "source_id": source.record_id,
                    "source_timestamp": source.timestamp.isoformat(),
                    "source_label": source.source_label,
                    "source_hash": source.source_hash,
                    "provenance": source.provenance.value,
                },
                "report_id,source_type,source_id",
            )
            await self._upsert(
                "athlete_timeline_events",
                {
                    "athlete_id": str(athlete_id),
                    "event_type": timeline_title.upper().replace(" ", "_"),
                    "source_type": source.source_type.value,
                    "source_id": source.record_id,
                    "event_time": source.timestamp.isoformat(),
                    "title": timeline_title,
                    "summary": "",
                    "severity": source.values.get("severity"),
                },
                "athlete_id,source_type,source_id",
            )

    async def _save_intelligence_snapshot(self, report_data: ReportData) -> None:
        period_start = report_data.date_range_start
        period_end = report_data.date_range_end
        if period_start is None or period_end is None:
            raise ValueError("Longitudinal reports require a bounded period.")
        if report_data.data_completeness is DataCompleteness.COMPLETE:
            snapshot_completeness = "HIGH"
        elif report_data.data_completeness is DataCompleteness.PARTIAL:
            snapshot_completeness = "MODERATE"
        elif report_data.data_completeness in {DataCompleteness.NO_DATA, DataCompleteness.NO_EVENTS}:
            snapshot_completeness = "INSUFFICIENT"
        else:
            snapshot_completeness = "LOW"
        summary = {
            "source_count": len(report_data.sources),
            "data_gaps": report_data.data_gaps,
            "longitudinal_insights": [
                insight.model_dump(mode="json") for insight in report_data.longitudinal_insights
            ],
        }
        existing = await self._rows(
            "athlete_intelligence_snapshots",
            {
                "athlete_id": f"eq.{report_data.athlete_id}",
                "report_id": f"eq.{report_data.report_id}",
                "calculation_version": "eq.longitudinal-v1",
                "select": "id",
                "limit": "1",
            },
        )
        if existing:
            snapshot_id = existing[0]["id"]
            await self._patch(
                "athlete_intelligence_snapshots",
                {"id": f"eq.{snapshot_id}", "athlete_id": f"eq.{report_data.athlete_id}"},
                {
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "data_completeness": snapshot_completeness,
                    "summary_json": summary,
                },
            )
        else:
            snapshot = await self._insert(
                "athlete_intelligence_snapshots",
                {
                    "athlete_id": str(report_data.athlete_id),
                    "report_id": str(report_data.report_id),
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "data_completeness": snapshot_completeness,
                    "calculation_version": "longitudinal-v1",
                    "summary_json": summary,
                },
            )
            snapshot_id = snapshot["id"]
        for insight in report_data.longitudinal_insights:
            await self._upsert(
                "athlete_intelligence_insights",
                {
                    "athlete_id": str(report_data.athlete_id),
                    "snapshot_id": snapshot_id,
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "insight_type": "TREND",
                    "statement": insight.statement,
                    "source_ids": insight.source_ids,
                    "evidence_strength": insight.evidence_strength.value,
                    "status": "ACTIVE",
                    "interpretation_source": "CALCULATED",
                },
                "snapshot_id,insight_type,statement",
            )

    async def _save_ai_output(
        self,
        athlete_id: UUID,
        report_id: UUID,
        provider: str,
        output: AIInterpretation,
        input_hash: str,
        latency_ms: int,
    ) -> None:
        await self._insert(
            "report_ai_outputs",
            {
                "athlete_id": str(athlete_id),
                "report_id": str(report_id),
                "provider": provider,
                "model": self.settings.gemini_model,
                "model_version": self.settings.gemini_model,
                "prompt_version": PROMPT_VERSION,
                "schema_version": SCHEMA_VERSION,
                "input_hash": input_hash,
                "structured_output": output.model_dump(mode="json"),
                "validation_status": "VALID",
                "safety_status": "PASSED",
                "latency_ms": latency_ms,
            },
        )

    async def _register_versions(self, report_type: ReportType) -> None:
        prompt_name = f"report-interpretation-{report_type.value.lower()}"
        prompt_hash = _sha256(f"{GLOBAL_SYSTEM_PROMPT}\n{feature_prompt(report_type)}")
        await self._upsert(
            "ai_prompt_registry",
            {
                "prompt_name": prompt_name,
                "version": PROMPT_VERSION,
                "purpose": f"Source-grounded interpretation for {report_type.value}",
                "prompt_hash": prompt_hash,
                "active": True,
            },
            "prompt_name,version",
        )
        await self._upsert(
            "report_schema_registry",
            {
                "schema_name": "report-ai",
                "version": SCHEMA_VERSION,
                "schema_json": AIInterpretation.model_json_schema(),
                "active": True,
            },
            "schema_name,version",
        )
        await self._upsert(
            "report_template_registry",
            {
                "template_name": "athlete-report",
                "version": self.settings.report_default_template_version,
                "active": True,
            },
            "template_name,version",
        )

    async def _stage(self, athlete_id: UUID, report_id: UUID, status: ReportStatus) -> None:
        await self._patch_report(athlete_id, report_id, {"status": status.value})
        await self._event(athlete_id, report_id, status.value, "COMPLETED")

    async def _set_ai_status(self, athlete_id: UUID, report_id: UUID, value: str) -> None:
        await self._patch_report(athlete_id, report_id, {"ai_status": value})

    async def _set_file_status(self, athlete_id: UUID, report_id: UUID, key: str, value: str) -> None:
        await self._patch_report(athlete_id, report_id, {key: value})

    async def _job_status(
        self,
        athlete_id: UUID,
        report_id: UUID,
        value: str,
        *,
        error_code: str | None = None,
        job_type: str = "REPORT_GENERATION",
    ) -> None:
        jobs = await self._rows(
            "report_jobs",
            {
                "athlete_id": f"eq.{athlete_id}",
                "report_id": f"eq.{report_id}",
                "job_type": f"eq.{job_type}",
                "status": "in.(QUEUED,RUNNING)",
                "select": "id",
                "order": "created_at.desc",
                "limit": "1",
            },
        )
        if jobs:
            patch: dict[str, Any] = {
                "status": value,
                "error_code": error_code,
                "attempts": 1,
            }
            if value == "RUNNING":
                patch["started_at"] = datetime.now(UTC).isoformat()
            if value in {"COMPLETED", "FAILED"}:
                patch["completed_at"] = datetime.now(UTC).isoformat()
            await self._patch(
                "report_jobs",
                {"id": f"eq.{jobs[0]['id']}", "athlete_id": f"eq.{athlete_id}"},
                patch,
            )

    async def _patch_latest_job(
        self, athlete_id: UUID, report_id: UUID, job_type: str, value: str
    ) -> None:
        await self._job_status(athlete_id, report_id, value, job_type=job_type)

    async def _event(
        self,
        athlete_id: UUID,
        report_id: UUID,
        stage: str,
        status: str,
        detail_code: str | None = None,
    ) -> None:
        await self._insert(
            "report_pipeline_events",
            {
                "athlete_id": str(athlete_id),
                "report_id": str(report_id),
                "stage": stage,
                "status": status,
                "detail_code": detail_code,
            },
        )

    async def _audit(
        self, athlete_id: UUID, actor_id: UUID, report_id: UUID, action: str
    ) -> None:
        await self._insert(
            "report_access_audit",
            {
                "athlete_id": str(athlete_id),
                "actor_id": str(actor_id),
                "report_id": str(report_id),
                "action": action,
            },
        )

    async def _report(self, athlete_id: UUID, report_id: UUID) -> dict[str, Any]:
        reports = await self._rows(
            "reports",
            {
                "id": f"eq.{report_id}",
                "athlete_id": f"eq.{athlete_id}",
                "select": "*",
                "limit": "1",
            },
        )
        if not reports:
            raise KeyError("Report not found.")
        return reports[0]

    async def _patch_report(self, athlete_id: UUID, report_id: UUID, values: dict[str, Any]) -> None:
        await self._patch(
            "reports",
            {"id": f"eq.{report_id}", "athlete_id": f"eq.{athlete_id}"},
            values,
        )

    async def _rows(self, table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        rows = await self.repository.rest("GET", table, params=params)
        return rows if isinstance(rows, list) else []

    async def _insert(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = await self.repository.rest("POST", table, payload=payload, prefer="return=representation")
        if not isinstance(rows, list) or not rows:
            raise RuntimeError(f"{table} insert returned no representation.")
        return rows[0]

    async def _upsert(self, table: str, payload: dict[str, Any], conflict: str) -> None:
        await self.repository.rest(
            "POST",
            table,
            params={"on_conflict": conflict},
            payload=payload,
            prefer="resolution=merge-duplicates,return=minimal",
        )

    async def _patch(self, table: str, filters: dict[str, str], payload: dict[str, Any]) -> None:
        await self.repository.rest(
            "PATCH",
            table,
            params=filters,
            payload=payload,
            prefer="return=minimal",
        )


def _with_default_period(request: ReportRequest) -> ReportRequest:
    report_type = request.report_type
    days = (
        7 if report_type.value.startswith("WEEKLY_")
        else 30 if report_type.value.startswith("MONTHLY_")
        else 366 if report_type in {ReportType.FULL_ATHLETE_REPORT, ReportType.DOCTOR_ATHLETE_REPORT}
        else None
    )
    if days is None:
        return request
    end = datetime.now(UTC)
    period_end = request.date_range_end or end
    period_start = request.date_range_start or period_end - timedelta(days=days)
    if request.date_range_start is not None and request.date_range_end is None:
        period_end = period_start + timedelta(days=days)
    elif request.date_range_end is not None and request.date_range_start is None:
        period_start = period_end - timedelta(days=days)
    return request.model_copy(update={"date_range_start": period_start, "date_range_end": period_end})


def _uses_longitudinal_data(report_type: ReportType) -> bool:
    return (
        report_type.value.startswith(("WEEKLY_", "MONTHLY_"))
        or report_type in {ReportType.FULL_ATHLETE_REPORT, ReportType.DOCTOR_ATHLETE_REPORT}
    )


def _previous_period(request: ReportRequest) -> ReportRequest | None:
    if request.date_range_start is None or request.date_range_end is None:
        return None
    duration = request.date_range_end - request.date_range_start
    if duration <= timedelta(0):
        return None
    previous_end = request.date_range_start - timedelta(microseconds=1)
    return request.model_copy(
        update={
            "date_range_start": previous_end - duration,
            "date_range_end": previous_end,
        }
    )


def _renumber_sources(
    current: list[ReportSource],
    previous: list[ReportSource],
    sections: list[ReportSection],
) -> tuple[list[ReportSource], list[ReportSource], list[ReportSection]]:
    mapping: dict[str, str] = {}
    current_sources: list[ReportSource] = []
    previous_sources: list[ReportSource] = []
    for index, source in enumerate(current, start=1):
        new_id = f"SOURCE-{index:03d}"
        mapping[source.source_id] = new_id
        current_sources.append(source.model_copy(update={"source_id": new_id}))
    for index, source in enumerate(previous, start=len(current_sources) + 1):
        new_id = f"SOURCE-{index:03d}"
        mapping[source.source_id] = new_id
        previous_sources.append(
            source.model_copy(
                update={
                    "source_id": new_id,
                    "source_label": f"Previous period · {source.source_label}",
                }
            )
        )
    remapped_sections = [
        section.model_copy(
            update={
                "values": [
                    value.model_copy(
                        update={"source_ids": [mapping[source_id] for source_id in value.source_ids]}
                    )
                    for value in section.values
                ]
            }
        )
        for section in sections
    ]
    return current_sources, previous_sources, remapped_sections


def _ai_safe_input(sources: list[Any]) -> dict[str, object]:
    source_values: list[dict[str, object]] = []
    for source in sources:
        values: dict[str, object] = {}
        for key, value in source.values.items():
            if isinstance(value, bool) or (isinstance(value, (int, float)) and key not in {"source_page", "pages_processed"}):
                values[key] = value
            elif isinstance(value, str) and _SAFE_ENUM.fullmatch(value):
                values[key] = value
        source_values.append(
            {
                "source_id": source.source_id,
                "source_type": source.source_type.value,
                "provenance": source.provenance.value,
                "values": values,
            }
        )
    return {"sources": source_values}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(value: str | bytes) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()
