from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BodyFindingState(StrEnum):
    NO_DATA = "NO_DATA"
    DATA_AVAILABLE = "DATA_AVAILABLE"
    RECENT_FINDING = "RECENT_FINDING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    HISTORICAL_FINDING = "HISTORICAL_FINDING"


class BodyRegion(BaseModel):
    id: UUID
    name: str
    system: str
    anatomical_identifier: str
    display_order: int


class BodyRegionFinding(BaseModel):
    id: UUID
    athlete_id: UUID
    body_region_id: UUID
    medical_report_id: UUID | None = None
    biomarker_measurement_id: UUID | None = None
    finding_type: str
    severity: str | None = None
    description: str
    source_type: str
    created_at: datetime


class BodyRegionFindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body_region_id: UUID
    finding_type: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=1000)


class BodyMapRegionResponse(BodyRegion):
    state: BodyFindingState = BodyFindingState.NO_DATA
    findings: list[BodyRegionFinding] = Field(default_factory=list)
