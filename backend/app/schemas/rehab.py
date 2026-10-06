from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator

from app.schemas.movement import MovementIntelligenceInput

class SessionStatus(StrEnum):
    PLANNED = "PLANNED"
    CALIBRATING = "CALIBRATING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class SessionSource(StrEnum):
    LIVE_SENSOR = "LIVE_SENSOR"
    SIMULATION = "SIMULATION"
    MANUAL = "MANUAL"


class MovementQuality(StrEnum):
    GOOD = "GOOD"
    MODERATE = "MODERATE"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class FatigueSignal(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ReadinessStatus(StrEnum):
    READY = "READY"
    READY_WITH_CAUTION = "READY_WITH_CAUTION"
    REST_RECOMMENDED = "REST_RECOMMENDED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class SensorPlacement(StrEnum):
    THIGH = "THIGH"
    SHANK = "SHANK"
    FOREARM = "FOREARM"
    UPPER_ARM = "UPPER_ARM"
    WAIST = "WAIST"
    CHEST = "CHEST"
    OTHER = "OTHER"


class RehabSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: UUID
    client_session_id: UUID | None = None
    program_id: UUID | None = None
    source: SessionSource = SessionSource.SIMULATION
    sensor_type: str | None = Field(default=None, max_length=80)
    sensor_placement: SensorPlacement | None = None
    device_id: UUID | None = None
    target_repetitions: int | None = Field(default=None, ge=1, le=200)

    @model_validator(mode="after")
    def manual_sessions_have_no_sensor(self) -> RehabSessionCreate:
        if self.source == SessionSource.MANUAL and (self.sensor_type or self.sensor_placement):
            raise ValueError("Manual sessions cannot include sensor fields.")
        if self.source == SessionSource.LIVE_SENSOR:
            if self.sensor_type != "MPU6050" or self.sensor_placement is None or self.device_id is None:
                raise ValueError("Live sensor sessions require an MPU6050, placement and registered device.")
        elif self.device_id is not None:
            raise ValueError("Only live sensor sessions can include a device.")
        return self


class RehabSessionTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: SessionStatus


class RepetitionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rep_number: int = Field(ge=1)
    started_at: datetime
    ended_at: datetime
    duration_ms: int = Field(ge=1)
    movement_phase: str | None = Field(default=None, max_length=40)
    quality: MovementQuality
    stability: MovementQuality
    smoothness: MovementQuality
    range_of_motion_signal: str | None = Field(default=None, max_length=40)
    abnormality: str | None = Field(default=None, max_length=120)
    source: SessionSource


class MovementMetricInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_name: str = Field(min_length=1, max_length=80)
    metric_value: float
    unit: str | None = Field(default=None, max_length=40)
    calculation_version: str = Field(min_length=1, max_length=40)


class MovementSummaryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: SessionSource
    sensor_placement: SensorPlacement | None = None
    device_id: UUID | None = None
    sample_count: int = Field(ge=0, le=100_000)
    target_repetitions: int | None = Field(default=None, ge=1, le=200)
    completed_repetitions: int = Field(ge=0, le=200)
    movement_quality: MovementQuality
    stability: MovementQuality
    smoothness: MovementQuality
    fatigue_signal: FatigueSignal
    session_duration_seconds: int = Field(ge=0, le=86_400)
    successful_requests: int = Field(default=0, ge=0, le=1_000_000)
    failed_requests: int = Field(default=0, ge=0, le=1_000_000)
    invalid_samples: int = Field(default=0, ge=0, le=1_000_000)
    measured_rate_hz: FiniteFloat | None = Field(default=None, ge=0, le=100)
    average_latency_ms: FiniteFloat | None = Field(default=None, ge=0, le=60_000)
    abnormal_events: list[Literal["CAUTION_MOVEMENT_SIGNAL", "REVIEW_REQUIRED"]] = Field(default_factory=list, max_length=50)
    repetitions: list[RepetitionResult] = Field(default_factory=list, max_length=200)
    metrics: list[MovementMetricInput] = Field(default_factory=list, max_length=100)
    movement_intelligence: MovementIntelligenceInput | None = None

    @model_validator(mode="after")
    def summary_matches_source_and_target(self) -> MovementSummaryCreate:
        if self.target_repetitions is not None and self.completed_repetitions > self.target_repetitions:
            raise ValueError("Completed repetitions cannot exceed the target.")
        if self.source == SessionSource.MANUAL and (self.sensor_placement is not None or self.sample_count):
            raise ValueError("Manual sessions cannot claim sensor samples or placement.")
        if self.source == SessionSource.LIVE_SENSOR and (self.sensor_placement is None or self.device_id is None):
            raise ValueError("Live sensor summaries require a placement and registered device.")
        if self.source != SessionSource.LIVE_SENSOR and self.device_id is not None:
            raise ValueError("Only live sensor summaries can include a device.")
        if self.source != SessionSource.LIVE_SENSOR and (
            self.successful_requests
            or self.failed_requests
            or self.invalid_samples
            or self.measured_rate_hz is not None
            or self.average_latency_ms is not None
        ):
            raise ValueError("Only live sensor summaries can include device request diagnostics.")
        if any(rep.source != self.source for rep in self.repetitions):
            raise ValueError("Each repetition source must match the session source.")
        if [rep.rep_number for rep in self.repetitions] != sorted({rep.rep_number for rep in self.repetitions}):
            raise ValueError("Repetition numbers must be unique and ordered.")
        if self.movement_intelligence is not None and self.source == SessionSource.MANUAL:
            raise ValueError("Movement intelligence cannot be attached to an unmeasured manual session.")
        return self


class FunctionalTestResultCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration_seconds: float | None = Field(default=None, gt=0, le=3600)
    stability: MovementQuality
    movement_quality: MovementQuality
    source: Literal["SIMULATION", "MANUAL"]
    notes: str | None = Field(default=None, max_length=1000)


class ReadinessEvaluate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    self_reported_status: Literal["FEELING_OK", "SORE", "FATIGUED", "PAIN_OR_CONCERN"] | None = None
    soreness: Literal["NONE", "MILD", "MODERATE", "SEVERE"] | None = None


class ReturnToSportEvaluate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    athlete_reported_status: Literal["NOT_READY", "PROGRESSING", "READY_FOR_REVIEW"] | None = None


class RehabProgramExercise(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    exercise_id: UUID
    order_index: int = Field(ge=0)
    sets: int = Field(ge=1, le=50)
    repetitions: int | None = Field(default=None, ge=1, le=200)
    duration_seconds: int | None = Field(default=None, ge=1, le=3600)
    rest_seconds: int = Field(ge=0, le=3600)
    required: bool = True
    target_quality: MovementQuality | None = None
    notes: str | None = None
    exercise: dict[str, object] | None = None


class RehabProgram(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: UUID
    athlete_id: UUID
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    goal: str | None = None
    stage: str | None = None
    stage_order: int | None = Field(default=None, ge=0)
    stages: list[dict[str, object]] = Field(default_factory=list)
    status: Literal["DRAFT", "ACTIVE", "COMPLETED", "PAUSED", "CANCELLED"]
    start_date: date | None = None
    target_end_date: date | None = None
    assigned_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
