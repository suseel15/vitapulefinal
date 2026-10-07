from app.reports.builders.common import SourceTable
from app.reports.schemas import ReportProvenance, SourceType

MEDICATION_TABLES = (
    SourceTable(
        "medications", SourceType.MEDICATION, "created_at", provenance=ReportProvenance.SELF_REPORTED,
        fields=("name", "dose", "frequency", "start_date", "end_date", "status", "created_at"),
        event_type="MEDICATION_RECORD",
    ),
)
