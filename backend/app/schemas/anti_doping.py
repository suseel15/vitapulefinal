from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class AntiDopingStatus(StrEnum):
    NO_KNOWN_MATCH = "NO_KNOWN_MATCH"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    POTENTIAL_PROHIBITED = "POTENTIAL_PROHIBITED"
    TUE_REVIEW = "TUE_REVIEW"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


class AntiDopingSource(BaseModel):
    source_name: str
    source_version: str | None = None
    effective_date: date | None = None
    retrieved_at: datetime | None = None
    verified: bool = False


class AntiDopingReview(BaseModel):
    id: UUID
    athlete_id: UUID
    status: AntiDopingStatus
    substance_name: str | None = None
    review_note: str | None = None
    source: AntiDopingSource | None = None
    created_at: datetime
