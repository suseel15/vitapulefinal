from app.reports.builders.common import SourceTable
from app.reports.schemas import ReportProvenance, SourceType

WELLBEING_TABLES = (
    SourceTable(
        "wellbeing_checkins", SourceType.WELLBEING, "created_at", provenance=ReportProvenance.SELF_REPORTED,
        fields=("energy", "stress", "fatigue", "soreness", "recovery_feeling", "mood_self_report", "source", "created_at"),
        event_type="WELLBEING_CHECKIN",
    ),
    SourceTable(
        "camera_wellbeing_features", SourceType.WELLBEING, "created_at", provenance=ReportProvenance.CALCULATED,
        fields=("session_id", "face_presence_ratio", "face_position_stability", "head_movement_magnitude", "head_movement_variability", "head_orientation_range", "capture_quality", "feature_schema_version", "source", "created_at"),
        event_type="CAMERA_WELLBEING",
    ),
    SourceTable(
        "sleep_records", SourceType.SLEEP, "end_time",
        fields=("start_time", "end_time", "duration_minutes", "quality_rating", "interruptions", "source", "source_id"),
        event_type="SLEEP_RECORD",
    ),
)
