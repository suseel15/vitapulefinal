from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class SkinScreeningResult(StrEnum):
    NO_CONCERNING_VISUAL_PATTERN = "NO_CONCERNING_VISUAL_PATTERN"
    REVIEW_RECOMMENDED = "REVIEW_RECOMMENDED"
    UNABLE_TO_ASSESS_RELIABLY = "UNABLE_TO_ASSESS_RELIABLY"
    POTENTIALLY_CONCERNING_VISUAL_PATTERN = "POTENTIALLY_CONCERNING_VISUAL_PATTERN"


class SkinScreeningRecord(BaseModel):
    id: UUID
    athlete_id: UUID
    result: SkinScreeningResult
    quality_status: str
    consent_purpose: str
    consented_at: datetime
    source_type: str
    retained_until: datetime | None = None
    created_at: datetime
    diagnostic_statement: None = None
