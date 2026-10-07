from app.reports.builders.common import SourceTable
from app.reports.schemas import ReportProvenance, SourceType

REHAB_TABLES = (
    SourceTable(
        "rehab_sessions", SourceType.REHAB, "started_at", provenance=ReportProvenance.LIVE_SENSOR,
        fields=("exercise_id", "program_id", "status", "source", "started_at", "ended_at", "session_duration_seconds", "completed_repetitions", "target_repetitions", "movement_quality", "stability", "smoothness", "fatigue_signal", "completion_rate"),
        event_type="REHAB_SESSION",
    ),
    SourceTable(
        "rehab_progress", SourceType.REHAB, "period_end", provenance=ReportProvenance.CALCULATED,
        fields=("stage", "metric_name", "metric_value", "unit", "source", "period_start", "period_end"),
        event_type="REHAB_PROGRESS",
    ),
    SourceTable(
        "functional_test_results", SourceType.REHAB, "created_at",
        fields=("functional_test_id", "session_id", "duration_seconds", "stability", "movement_quality", "source", "result", "created_at"),
        event_type="FUNCTIONAL_TEST",
    ),
    SourceTable(
        "readiness_assessments", SourceType.REHAB, "created_at", provenance=ReportProvenance.CALCULATED,
        fields=("session_id", "status", "factors", "source", "created_at"),
        event_type="READINESS_ASSESSMENT",
    ),
    SourceTable(
        "return_to_sport_assessments", SourceType.REHAB, "created_at", provenance=ReportProvenance.CALCULATED,
        fields=("program_id", "stage", "status", "clinician_review_status", "source", "created_at"),
        event_type="RETURN_TO_SPORT_REVIEW",
    ),
)
