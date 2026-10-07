from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ShortText = Annotated[str, Field(min_length=1, max_length=200)]
LongText = Annotated[str, Field(max_length=4000)]


class DoctorProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: ShortText | None = None
    professional_title: Annotated[str, Field(max_length=120)] | None = None
    specialization: Annotated[str, Field(max_length=200)] | None = None
    phone: Annotated[str, Field(max_length=40)] | None = None
    clinic_name: Annotated[str, Field(max_length=200)] | None = None
    clinic_address: Annotated[str, Field(max_length=500)] | None = None
    years_experience: int | None = Field(default=None, ge=0, le=80)
    sports_specialties: list[Annotated[str, Field(min_length=1, max_length=80)]] | None = Field(default=None, max_length=20)


class InvitationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: Annotated[str, Field(min_length=3, max_length=254)]
    relationship_type: Literal["PRIMARY_DOCTOR", "SPORTS_DOCTOR", "PHYSIOTHERAPIST", "REHAB_SPECIALIST", "OTHER"] = "OTHER"
    message: Annotated[str, Field(max_length=500)] = ""


class InvitationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accept: bool


class CarePlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ShortText
    description: LongText = ""
    rehab_stage: Annotated[str, Field(max_length=120)] | None = None
    start_date: date | None = None
    target_review_date: date | None = None
    end_date: date | None = None
    change_summary: Annotated[str, Field(min_length=1, max_length=1000)] = "Initial care plan created."
    status: Literal["DRAFT", "ACTIVE"] = "DRAFT"


class CarePlanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ShortText | None = None
    description: LongText | None = None
    status: Literal["DRAFT", "ACTIVE", "PAUSED", "REVIEW_REQUIRED", "COMPLETED", "CANCELLED", "ARCHIVED"] | None = None
    rehab_stage: Annotated[str, Field(max_length=120)] | None = None
    start_date: date | None = None
    target_review_date: date | None = None
    end_date: date | None = None
    change_summary: Annotated[str, Field(min_length=1, max_length=1000)]


class CareGoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ShortText
    description: Annotated[str, Field(max_length=2000)] = ""
    priority: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    target_date: date | None = None
    measurement_type: Annotated[str, Field(max_length=80)] | None = None
    target_value: float | None = None


class CareItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: Literal["EXERCISE", "PROGRAM", "FUNCTIONAL_TEST", "RECOVERY_ACTION", "FOLLOW_UP", "DOCTOR_NOTE", "PATIENT_INSTRUCTION", "REVIEW"]
    title: ShortText
    description: LongText = ""
    linked_entity: UUID | None = None
    sets: int | None = Field(default=None, ge=1, le=50)
    repetitions: int | None = Field(default=None, ge=1, le=200)
    duration_seconds: int | None = Field(default=None, ge=1, le=86400)
    frequency: Annotated[str, Field(max_length=120)] | None = None
    rest_seconds: int | None = Field(default=None, ge=0, le=3600)
    intensity: Annotated[str, Field(max_length=120)] | None = None
    sensor_placement: Annotated[str, Field(max_length=40)] | None = None
    start_date: date | None = None
    end_date: date | None = None
    instructions: Annotated[str, Field(max_length=4000)] = ""
    restrictions: Annotated[str, Field(max_length=2000)] = ""
    due_date: date | None = None
    review_date: date | None = None
    priority: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"


class ProgramExerciseAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: UUID
    sets: int = Field(ge=1, le=50)
    repetitions: int | None = Field(default=None, ge=1, le=200)
    duration_seconds: int | None = Field(default=None, ge=1, le=3600)
    rest_seconds: int = Field(default=30, ge=0, le=3600)
    required: bool = True
    notes: Annotated[str, Field(max_length=1000)] = ""


class RehabProgramAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ShortText
    description: LongText = ""
    goal: Annotated[str, Field(max_length=500)] = ""
    stage: Annotated[str, Field(max_length=120)] | None = None
    start_date: date | None = None
    target_end_date: date | None = None
    exercises: list[ProgramExerciseAssignment] = Field(min_length=1, max_length=30)


class DoctorNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note_type: Literal["CLINICAL_NOTE", "REHAB_NOTE", "MOVEMENT_NOTE", "SAFETY_NOTE", "FOLLOW_UP_NOTE", "GENERAL_NOTE"]
    title: ShortText
    content: Annotated[str, Field(min_length=1, max_length=10000)]
    visibility: Literal["INTERNAL_ONLY", "ATHLETE_VISIBLE"] = "INTERNAL_ONLY"


class DoctorNoteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ShortText
    content: Annotated[str, Field(min_length=1, max_length=10000)]
    visibility: Literal["INTERNAL_ONLY", "ATHLETE_VISIBLE"] = "INTERNAL_ONLY"
    edit_reason: Annotated[str, Field(min_length=1, max_length=1000)]


class DoctorReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_type: Literal["HEALTH_REPORT", "REHAB_SESSION", "FUNCTIONAL_TEST", "READINESS", "RETURN_TO_SPORT", "SAFETY_EVENT", "WELLBEING", "CARE_PLAN", "LONGITUDINAL_INTELLIGENCE", "GENERAL"]
    subject_type: Annotated[str, Field(min_length=1, max_length=100)]
    subject_id: UUID | None = None
    summary: Annotated[str, Field(min_length=1, max_length=4000)]
    clinical_interpretation: Annotated[str, Field(max_length=8000)] = ""
    recommendations: Annotated[str, Field(max_length=8000)] = ""
    decision: Annotated[str, Field(max_length=80)] | None = None
    source_ids: list[Annotated[str, Field(min_length=1, max_length=80)]] = Field(default_factory=list, max_length=100)
    next_review_date: date | None = None


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_type: Literal["GENERAL", "CARE_PLAN", "REHAB", "FOLLOW_UP", "REPORT"] = "GENERAL"
    body: Annotated[str, Field(min_length=1, max_length=4000)]
