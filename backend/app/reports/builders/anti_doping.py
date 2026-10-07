from app.reports.builders.common import SourceTable
from app.reports.schemas import ReportProvenance, SourceType

ANTI_DOPING_TABLES = (
    SourceTable(
        "anti_doping_reviews", SourceType.ANTI_DOPING, "created_at", provenance=ReportProvenance.CALCULATED,
        fields=("substance_name", "status", "created_at"),
        event_type="ANTI_DOPING_REVIEW",
    ),
)
