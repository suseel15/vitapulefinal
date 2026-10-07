from app.reports.builders.common import SourceTable
from app.reports.schemas import ReportProvenance, SourceType
from app.reports.builders.anti_doping import ANTI_DOPING_TABLES
from app.reports.builders.health import HEALTH_TABLES
from app.reports.builders.medication import MEDICATION_TABLES
from app.reports.builders.movement import MOVEMENT_TABLES
from app.reports.builders.nutrition import NUTRITION_TABLES
from app.reports.builders.recovery import RECOVERY_TABLES
from app.reports.builders.rehab import REHAB_TABLES
from app.reports.builders.safety import SAFETY_TABLES
from app.reports.builders.skin_screening import SKIN_SCREENING_TABLES
from app.reports.builders.wellbeing import WELLBEING_TABLES

ATHLETE_SUMMARY_TABLES = (
    SourceTable(
        "health_data_sync_runs", SourceType.CONNECTIVITY, "completed_at",
        provenance=ReportProvenance.WATCH_DERIVED,
        fields=("source", "status", "records_found", "records_imported", "records_skipped", "records_failed", "data_types", "started_at", "completed_at"),
        event_type="HEALTH_DATA_SYNC",
    ),
    SourceTable(
        "unified_heart_rate_records", SourceType.CONNECTIVITY, "end_time",
        provenance=ReportProvenance.WATCH_DERIVED,
        fields=("start_time", "end_time", "average_bpm", "sample_count", "measurement_type", "source", "source_application"),
        event_type="HEART_RATE_RECORD",
    ),
    SourceTable(
        "unified_activity_records", SourceType.CONNECTIVITY, "end_time",
        provenance=ReportProvenance.WATCH_DERIVED,
        fields=("start_time", "end_time", "count", "source", "source_record_id", "source_application"),
        event_type="ACTIVITY_RECORD",
    ),
    *HEALTH_TABLES,
    *REHAB_TABLES,
    *MOVEMENT_TABLES,
    *WELLBEING_TABLES,
    *RECOVERY_TABLES,
    *SAFETY_TABLES,
    *NUTRITION_TABLES,
    *MEDICATION_TABLES,
    *ANTI_DOPING_TABLES,
    *SKIN_SCREENING_TABLES,
)
