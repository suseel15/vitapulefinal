from app.reports.builders.common import SourceTable
from app.reports.schemas import ReportProvenance, SourceType

SAFETY_TABLES = (
    SourceTable(
        "movement_events", SourceType.SAFETY, "timestamp", provenance=ReportProvenance.CALCULATED,
        fields=("session_id", "timestamp", "event_type", "severity", "source"),
        event_type="SAFETY_SIGNAL",
    ),
)
