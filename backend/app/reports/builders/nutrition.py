from app.reports.builders.common import SourceTable
from app.reports.schemas import ReportProvenance, SourceType

NUTRITION_TABLES = (
    SourceTable(
        "nutrition_entries", SourceType.NUTRITION, "entry_date", provenance=ReportProvenance.USER_ENTERED,
        fields=("entry_date", "entry_type", "name", "calories", "protein_g", "carbohydrates_g", "fat_g", "fiber_g", "hydration_ml", "source_type"),
        event_type="NUTRITION_ENTRY",
    ),
)
