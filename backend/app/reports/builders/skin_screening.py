from app.reports.builders.common import SourceTable
from app.reports.schemas import ReportProvenance, SourceType

SKIN_SCREENING_TABLES = (
    SourceTable(
        "skin_screenings", SourceType.SKIN, "created_at", provenance=ReportProvenance.SELF_REPORTED,
        fields=("result", "quality_status", "source_type", "created_at"),
        event_type="SKIN_SCREENING",
    ),
)
