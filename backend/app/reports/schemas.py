from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ReportType(StrEnum):
    MEDICAL_REPORT_ANALYSIS = "MEDICAL_REPORT_ANALYSIS"
    BIOMARKER_REPORT = "BIOMARKER_REPORT"
    BODY_MAP_REPORT = "BODY_MAP_REPORT"
    HEALTH_INTELLIGENCE_REPORT = "HEALTH_INTELLIGENCE_REPORT"
    REHAB_SESSION_REPORT = "REHAB_SESSION_REPORT"
    MOVEMENT_ANALYSIS_REPORT = "MOVEMENT_ANALYSIS_REPORT"
    EXERCISE_PROGRESS_REPORT = "EXERCISE_PROGRESS_REPORT"
    FUNCTIONAL_TEST_REPORT = "FUNCTIONAL_TEST_REPORT"
    READINESS_REPORT = "READINESS_REPORT"
    RETURN_TO_SPORT_REPORT = "RETURN_TO_SPORT_REPORT"
    WELLBEING_CHECKIN_REPORT = "WELLBEING_CHECKIN_REPORT"
    CAMERA_WELLBEING_REPORT = "CAMERA_WELLBEING_REPORT"
    SLEEP_REPORT = "SLEEP_REPORT"
    RECOVERY_REPORT = "RECOVERY_REPORT"
    CONNECTIVITY_REPORT = "CONNECTIVITY_REPORT"
    NUTRITION_REPORT = "NUTRITION_REPORT"
    MEDICATION_REPORT = "MEDICATION_REPORT"
    ANTI_DOPING_REPORT = "ANTI_DOPING_REPORT"
    SKIN_SCREENING_REPORT = "SKIN_SCREENING_REPORT"
    SAFETY_INCIDENT_REPORT = "SAFETY_INCIDENT_REPORT"
    WEEKLY_HEALTH_REPORT = "WEEKLY_HEALTH_REPORT"
    WEEKLY_REHAB_REPORT = "WEEKLY_REHAB_REPORT"
    WEEKLY_WELLBEING_REPORT = "WEEKLY_WELLBEING_REPORT"
    WEEKLY_ATHLETE_REPORT = "WEEKLY_ATHLETE_REPORT"
    MONTHLY_HEALTH_REPORT = "MONTHLY_HEALTH_REPORT"
    MONTHLY_REHAB_REPORT = "MONTHLY_REHAB_REPORT"
    MONTHLY_ATHLETE_REPORT = "MONTHLY_ATHLETE_REPORT"
    DOCTOR_ATHLETE_REPORT = "DOCTOR_ATHLETE_REPORT"
    FULL_ATHLETE_REPORT = "FULL_ATHLETE_REPORT"


class ReportStatus(StrEnum):
    REQUESTED = "REQUESTED"
    QUEUED = "QUEUED"
    COLLECTING_DATA = "COLLECTING_DATA"
    VALIDATING_INPUT = "VALIDATING_INPUT"
    GENERATING_AI = "GENERATING_AI"
    VALIDATING_AI = "VALIDATING_AI"
    BUILDING_REPORT = "BUILDING_REPORT"
    RENDERING_HTML = "RENDERING_HTML"
    RENDERING_PDF = "RENDERING_PDF"
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ReportProvenance(StrEnum):
    DIRECTLY_REPORTED = "DIRECTLY_REPORTED"
    SELF_REPORTED = "SELF_REPORTED"
    WATCH_DERIVED = "WATCH_DERIVED"
    LIVE_SENSOR = "LIVE_SENSOR"
    CALCULATED = "CALCULATED"
    MODEL_INFERRED = "MODEL_INFERRED"
    AI_INTERPRETED = "AI_INTERPRETED"
    CLINICIAN_ENTERED = "CLINICIAN_ENTERED"
    SIMULATION = "SIMULATION"
    USER_ENTERED = "USER_ENTERED"


class SourceType(StrEnum):
    HEALTH = "HEALTH"
    REHAB = "REHAB"
    MOVEMENT = "MOVEMENT"
    WELLBEING = "WELLBEING"
    SLEEP = "SLEEP"
    RECOVERY = "RECOVERY"
    CONNECTIVITY = "CONNECTIVITY"
    SAFETY = "SAFETY"
    NUTRITION = "NUTRITION"
    MEDICATION = "MEDICATION"
    ANTI_DOPING = "ANTI_DOPING"
    SKIN = "SKIN"


class EvidenceStrength(StrEnum):
    DIRECT = "DIRECT"
    SUPPORTED = "SUPPORTED"
    LIMITED = "LIMITED"
    INSUFFICIENT = "INSUFFICIENT"


class RecommendationPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DataCompleteness(StrEnum):
    NO_EVENTS = "NO_EVENTS"
    NO_DATA = "NO_DATA"
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"


class AIObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation: Annotated[str, Field(min_length=1, max_length=500)]
    source_ids: list[str] = Field(min_length=1, max_length=10)
    source_type: SourceType
    evidence_strength: EvidenceStrength


class AIRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: Annotated[str, Field(min_length=1, max_length=400)]
    reason: Annotated[str, Field(min_length=1, max_length=400)]
    source_ids: list[str] = Field(min_length=1, max_length=10)
    priority: RecommendationPriority


class AIInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: Annotated[str, Field(min_length=1, max_length=1000)]
    summary_source_ids: list[str] = Field(min_length=1, max_length=10)
    key_observations: list[AIObservation] = Field(max_length=7)
    patterns: list[AIObservation] = Field(max_length=7)
    explanations: list[AIObservation] = Field(max_length=7)
    recommendations: list[AIRecommendation] = Field(max_length=5)
    limitations: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(max_length=10)
    follow_up: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(max_length=5)


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    report_type: ReportType = Field(alias="reportType")
    feature_id: UUID | None = Field(default=None, alias="featureId")
    source_ids: list[UUID] = Field(default_factory=list, alias="sourceIds", max_length=100)
    date_range_start: datetime | None = Field(default=None, alias="dateRangeStart")
    date_range_end: datetime | None = Field(default=None, alias="dateRangeEnd")
    include_ai: bool = Field(default=True, alias="includeAi")
    include_pdf: bool = Field(default=True, alias="includePdf")
    include_email: bool = Field(default=False, alias="includeEmail")
    recipient: str | None = Field(default=None, max_length=254)
    idempotency_key: str | None = Field(default=None, alias="idempotencyKey", max_length=100)

    @field_validator("recipient")
    @classmethod
    def validate_recipient(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return EmailReportRequest.validate_recipient(value)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        if not candidate or not all(character.isalnum() or character in "-_." for character in candidate):
            raise ValueError("The idempotency key contains unsupported characters.")
        return candidate

    @model_validator(mode="after")
    def validate_request(self) -> "ReportRequest":
        if self.date_range_start and self.date_range_end:
            if self.date_range_end < self.date_range_start:
                raise ValueError("Report end date must be after its start date.")
            if (self.date_range_end - self.date_range_start).days > 366:
                raise ValueError("Report date ranges are limited to 366 days.")
        if self.include_email and not self.recipient:
            raise ValueError("An explicit recipient is required when email is requested.")
        if self.include_email and not self.include_pdf:
            raise ValueError("A PDF report is required for email delivery.")
        return self


class ReportSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    source_id: str
    record_id: str
    timestamp: datetime
    source_label: str
    provenance: ReportProvenance
    source_hash: str
    values: dict[str, object]


class ReportValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: str
    source_ids: list[str] = Field(default_factory=list)
    provenance: ReportProvenance


class ReportSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: SourceType
    title: str
    values: list[ReportValue] = Field(default_factory=list)


class LongitudinalInsight(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    source_type: SourceType
    current_average: float
    previous_average: float
    current_count: int = Field(ge=3)
    previous_count: int = Field(ge=3)
    direction: str
    statement: str
    source_ids: list[str] = Field(min_length=1, max_length=10)
    evidence_strength: EvidenceStrength


class SourceCategorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    source_count: int = Field(ge=0)
    latest_timestamp: datetime | None = None
    completeness: DataCompleteness


class ReportData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: UUID
    athlete_id: UUID
    requested_by: UUID
    report_type: ReportType
    title: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    date_range_start: datetime | None = None
    date_range_end: datetime | None = None
    sections: list[ReportSection]
    sources: list[ReportSource]
    longitudinal_insights: list[LongitudinalInsight] = Field(default_factory=list)
    source_categories: list[SourceCategorySummary]
    data_completeness: DataCompleteness
    data_gaps: list[str]
    factual_summary: str
    limitations: list[str]
    report_version: str = "v1"
    template_version: str = "v1"
    ai_interpretation: AIInterpretation | None = None
    ai_status: str = "UNAVAILABLE"

    @model_validator(mode="after")
    def validate_sources(self) -> "ReportData":
        known = {source.source_id for source in self.sources}
        if any(source_id not in known for section in self.sections for value in section.values for source_id in value.source_ids):
            raise ValueError("A factual report value references an unknown source.")
        if any(source_id not in known for insight in self.longitudinal_insights for source_id in insight.source_ids):
            raise ValueError("A longitudinal insight references an unknown source.")
        return self


class ReportCreateResponse(BaseModel):
    report_id: UUID = Field(alias="reportId")
    status: ReportStatus
    status_url: str = Field(alias="statusUrl")


class EmailReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient: str = Field(min_length=3, max_length=254)

    @field_validator("recipient")
    @classmethod
    def validate_recipient(cls, value: str) -> str:
        import re

        candidate = value.strip()
        if not re.fullmatch(r"[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+", candidate):
            raise ValueError("Enter a valid email address.")
        return candidate
