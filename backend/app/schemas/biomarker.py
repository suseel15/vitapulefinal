from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.medical_report import SourceType


class BiomarkerMeasurement(BaseModel):
    id: UUID
    athlete_id: UUID
    medical_report_id: UUID | None = None
    biomarker_name: str
    canonical_name: str | None = None
    standard_code: str | None = None
    value_numeric: float | None = None
    value_text: str | None = None
    unit: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    abnormal_flag: str | None = None
    collection_date: date | None = None
    source_page: int | None = None
    source_text: str | None = None
    source_type: SourceType
    extraction_method: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    created_at: datetime


class BiomarkerSummary(BaseModel):
    biomarker_name: str
    canonical_name: str | None = None
    latest: BiomarkerMeasurement
    measurement_count: int = Field(ge=1)
    trend: str
    trend_available: bool
    measurements: list[BiomarkerMeasurement]


class BiomarkerDetail(BaseModel):
    biomarker_name: str
    latest: BiomarkerMeasurement | None = None
    measurements: list[BiomarkerMeasurement] = Field(default_factory=list)
    trend: str = "INSUFFICIENT_DATA"
    trend_available: bool = False
    missing_value_label: str | None = None
