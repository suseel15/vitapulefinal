from app.reports.builders.common import SourceTable
from app.reports.schemas import ReportProvenance, SourceType

RECOVERY_TABLES = (
    SourceTable(
        "recovery_records", SourceType.RECOVERY, "date", provenance=ReportProvenance.CALCULATED,
        fields=("date", "recovery_state", "supporting_factors", "calculation_version", "source"),
        event_type="RECOVERY_RECORD",
    ),
    SourceTable(
        "unified_sleep_records", SourceType.SLEEP, "end_time", provenance=ReportProvenance.WATCH_DERIVED,
        fields=("start_time", "end_time", "duration_minutes", "source", "source_record_id", "source_application"),
        event_type="SLEEP_RECORD",
    ),
)
