from app.reports.builders.common import SourceTable
from app.reports.schemas import ReportProvenance, SourceType

HEALTH_TABLES = (
    SourceTable(
        "medical_reports", SourceType.HEALTH, "uploaded_at", provenance=ReportProvenance.DIRECTLY_REPORTED,
        fields=("original_filename", "report_date", "uploaded_at", "processing_status", "ocr_status", "extraction_status", "analysis_status", "ocr_quality", "pages_processed"),
        event_type="MEDICAL_REPORT",
    ),
    SourceTable(
        "biomarker_measurements", SourceType.HEALTH, "collection_date", provenance=ReportProvenance.DIRECTLY_REPORTED,
        fields=("biomarker_name", "canonical_name", "value_numeric", "value_text", "unit", "reference_low", "reference_high", "abnormal_flag", "collection_date", "source_type", "source_page", "confidence"),
        event_type="BIOMARKER_MEASUREMENT",
    ),
    SourceTable(
        "body_region_findings", SourceType.HEALTH, "created_at",
        fields=("body_region_id", "medical_report_id", "biomarker_measurement_id", "finding_type", "severity", "source_type"),
        event_type="BODY_MAP_FINDING",
    ),
    SourceTable(
        "health_intelligence_items", SourceType.HEALTH, "created_at", provenance=ReportProvenance.CALCULATED,
        fields=("item_type", "category", "status", "observed_at", "created_at", "source_ids"),
        event_type="HEALTH_INTELLIGENCE",
    ),
)
