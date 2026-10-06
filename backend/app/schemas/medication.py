from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class MedicationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class MedicationSource(StrEnum):
    USER_ENTERED = "USER_ENTERED"
    MEDICAL_REPORT = "MEDICAL_REPORT"
    DOCTOR_ENTERED = "DOCTOR_ENTERED"


class MedicationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    dose: str | None = Field(default=None, max_length=120)
    frequency: str | None = Field(default=None, max_length=160)
    start_date: date | None = None
    end_date: date | None = None
    reason: str | None = Field(default=None, max_length=1000)
    status: MedicationStatus = MedicationStatus.ACTIVE
    source_type: MedicationSource = MedicationSource.USER_ENTERED
    medical_report_id: UUID | None = None


class MedicationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    dose: str | None = Field(default=None, max_length=120)
    frequency: str | None = Field(default=None, max_length=160)
    start_date: date | None = None
    end_date: date | None = None
    reason: str | None = Field(default=None, max_length=1000)
    status: MedicationStatus | None = None


class MedicationRecord(MedicationCreate):
    id: UUID
    athlete_id: UUID
    created_at: datetime
    updated_at: datetime
