import hashlib
import logging
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, HTTPException, status

from app.core.config import Settings
from app.repositories.medical_report_repository import MedicalReportRepository
from app.repositories.supabase import SupabaseRepository
from app.schemas.medical_report import OCRQuality
from app.services.report_extraction import extract_structured_report, to_measurement_rows
from app.services.report_ocr import (
    OCRExecutionError,
    OCRUnavailableError,
    process_report_ocr,
    validate_report_file,
)

logger = logging.getLogger(__name__)
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9 ._()\-]+")


def _safe_filename(filename: str) -> str:
    leaf_name = filename.replace("\\", "/").split("/")[-1]
    sanitized = SAFE_FILENAME.sub("_", leaf_name).strip(" .")
    if not sanitized or sanitized in {".", ".."}:
        sanitized = "medical-report"
    return sanitized[:255]


def _admin_repository(settings: Settings) -> SupabaseRepository:
    return SupabaseRepository(settings, "service-role", service_role=True)


async def upload_medical_report(
    *,
    athlete_id: UUID,
    content: bytes,
    filename: str,
    mime_type: str,
    settings: Settings,
    background_tasks: BackgroundTasks,
) -> dict:
    detected_mime = validate_report_file(content, filename, mime_type, settings.max_upload_size_mb)
    if not settings.supabase_storage_is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Private report storage is not configured.",
        )
    admin = _admin_repository(settings)
    reports = MedicalReportRepository(admin, athlete_id)
    digest = hashlib.sha256(content).hexdigest()
    duplicate = await reports.find_by_hash(digest)
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "This report appears to have already been uploaded.",
                "existing_report_id": duplicate["id"],
            },
        )

    report_id = uuid4()
    safe_name = _safe_filename(filename)
    storage_path = f"{athlete_id}/{report_id}/{safe_name}"
    await admin.upload_object(settings.medical_report_bucket, storage_path, content, detected_mime)
    try:
        report = await reports.create(
            {
                "id": str(report_id),
                "original_filename": safe_name,
                "mime_type": detected_mime,
                "file_size": len(content),
                "file_sha256": digest,
                "consent_purpose": "HEALTH_REPORT_PROCESSING",
                "consented_at": datetime.now(UTC).isoformat(),
                "storage_bucket": settings.medical_report_bucket,
                "storage_path": storage_path,
                "processing_status": "UPLOADED",
                "ocr_status": "PENDING",
                "extraction_status": "PENDING",
                "analysis_status": "PENDING",
            }
        )
    except Exception:
        try:
            await admin.delete_object(settings.medical_report_bucket, storage_path)
        except Exception:
            logger.exception("Failed to clean up private report object after report-record creation failed.")
        raise

    background_tasks.add_task(process_medical_report, report_id, athlete_id, settings)
    return report


async def process_medical_report(report_id: UUID, athlete_id: UUID, settings: Settings) -> None:
    admin = _admin_repository(settings)
    repository = MedicalReportRepository(admin, athlete_id)
    try:
        report = await repository.get(report_id)
        if report is None:
            raise RuntimeError("The uploaded report record was not found.")
        await repository.update(
            report_id,
            {
                "processing_status": "OCR_PROCESSING",
                "ocr_status": "PROCESSING",
                "error_code": None,
            },
        )
        content = await admin.download_object(report["storage_bucket"], report["storage_path"])
        ocr_result = await process_report_ocr(content, report["mime_type"], settings)
        await repository.update(
            report_id,
            {
                "ocr_status": "COMPLETED" if ocr_result.quality != OCRQuality.LOW_QUALITY else "LOW_QUALITY",
                "ocr_quality": ocr_result.quality.value,
                "ocr_engine": ocr_result.ocr_engine,
                "ocr_version": ocr_result.ocr_version,
                "ocr_confidence": ocr_result.ocr_confidence,
                "pages_processed": ocr_result.pages_processed,
                "text_length": ocr_result.text_length,
                "processing_status": "EXTRACTING",
                "extraction_status": "PROCESSING",
            },
        )
        await repository.insert_pages(
            [
                {
                    "athlete_id": str(athlete_id),
                    "medical_report_id": str(report_id),
                    "page_number": page.page_number,
                    "extracted_text": page.text,
                    "extraction_method": ocr_result.ocr_engine,
                }
                for page in ocr_result.pages
            ]
        )
        extraction = extract_structured_report(ocr_result)
        measurements = to_measurement_rows(extraction, athlete_id, report_id)
        from app.repositories.biomarker_repository import BiomarkerRepository

        await BiomarkerRepository(admin, athlete_id).insert_measurements(measurements)

        warnings = []
        if ocr_result.quality == OCRQuality.LOW_QUALITY:
            warnings.append("LOW_QUALITY_TEXT")
        if not measurements:
            warnings.append("NO_BIOMARKERS_EXTRACTED")
        await repository.update(
            report_id,
            {
                "processing_status": "COMPLETED",
                "extraction_status": "COMPLETED",
                "analysis_status": "PENDING",
                "report_date": extraction.report_date.isoformat() if extraction.report_date else None,
                "data_quality_warnings": warnings,
                "processed_at": datetime.now(UTC).isoformat(),
            },
        )
    except OCRUnavailableError:
        logger.warning("Report OCR is unavailable for report %s.", report_id)
        await repository.update(
            report_id,
            {
                "processing_status": "FAILED",
                "ocr_status": "FAILED",
                "error_code": "OCR_UNAVAILABLE",
            },
        )
    except OCRExecutionError as error:
        error_code = "OCR_TIMEOUT" if "timed out" in str(error).lower() else "OCR_FAILED"
        logger.warning("Report OCR failed for report %s (%s).", report_id, error_code)
        await repository.update(
            report_id,
            {
                "processing_status": "FAILED",
                "ocr_status": "FAILED",
                "error_code": error_code,
            },
        )
    except Exception:
        logger.exception("Medical report processing failed for report %s.", report_id)
        await repository.update(
            report_id,
            {
                "processing_status": "FAILED",
                "error_code": "PROCESSING_FAILED",
            },
        )
