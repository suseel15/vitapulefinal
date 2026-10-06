from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.anti_doping import AntiDopingStatus
from app.schemas.medical_report import MedicalReportResponse


class HealthOverview(BaseModel):
    latest_report: MedicalReportResponse | None = None
    tracked_biomarker_count: int = Field(ge=0)
    recent_findings: list[dict[str, object]] = Field(default_factory=list)
    recent_health_events: list[dict[str, object]] = Field(default_factory=list)
    medication_count: int = Field(ge=0)
    anti_doping_review_status: AntiDopingStatus = AntiDopingStatus.INSUFFICIENT_INFORMATION
    skin_screening_status: str = "NOT_AVAILABLE"
    last_synchronized_at: datetime | None = None


class HealthReportData(BaseModel):
    report_type: str
    athlete_id: UUID
    source_ids: list[UUID] = Field(default_factory=list)
    summary: str | None = None


class HealthReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_type: str = Field(
        pattern="^(MEDICAL_REPORT_ANALYSIS|BIOMARKER_REPORT|BODY_MAP_REPORT|HEALTH_INTELLIGENCE_REPORT|NUTRITION_REPORT|MEDICATION_REPORT|ANTI_DOPING_REVIEW|SKIN_SCREENING_REPORT|FULL_HEALTH_REPORT)$"
    )
    source_ids: list[UUID] = Field(min_length=1, max_length=100)


class HealthReportRecord(BaseModel):
    id: UUID
    athlete_id: UUID
    report_type: str
    source_ids: list[UUID]
    status: str
    summary: str | None = None
    created_at: datetime
    updated_at: datetime
