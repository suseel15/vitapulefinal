from app.reports.builders.common import SourceTable
from app.reports.schemas import ReportProvenance, SourceType

MOVEMENT_TABLES = (
    SourceTable(
        "movement_quality_results", SourceType.MOVEMENT, "created_at",
        provenance=ReportProvenance.MODEL_INFERRED,
        fields=("session_id", "movement_quality", "stability", "smoothness", "fatigue_signal", "source", "calculation_version"),
        event_type="MOVEMENT_ANALYSIS",
    ),
    SourceTable(
        "movement_metrics", SourceType.MOVEMENT, "created_at", id_column="session_id",
        provenance=ReportProvenance.CALCULATED,
        fields=("session_id", "metric_name", "metric_value", "unit", "source", "created_at"),
        event_type="MOVEMENT_METRIC",
    ),
    SourceTable(
        "movement_predictions", SourceType.MOVEMENT, "created_at", provenance=ReportProvenance.MODEL_INFERRED,
        fields=("session_id", "prediction_type", "prediction", "model_name", "model_version", "source", "timestamp"),
        event_type="MOVEMENT_PREDICTION",
    ),
)
