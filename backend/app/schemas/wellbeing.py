from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator


class WellbeingSource(StrEnum):
    SELF_REPORTED = "SELF_REPORTED"
    CAMERA_OBSERVED = "CAMERA_OBSERVED"
    WATCH_DERIVED = "WATCH_DERIVED"
    CALCULATED = "CALCULATED"
    AI_INTERPRETED = "AI_INTERPRETED"


class CheckInCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    energy: int = Field(ge=1, le=5)
    stress: int = Field(ge=1, le=5)
    fatigue: int = Field(ge=1, le=5)
    soreness: int = Field(ge=1, le=5)
    recovery_feeling: int = Field(ge=1, le=5)
    mood_self_report: int | None = Field(default=None, ge=1, le=5)
    note: str | None = Field(default=None, max_length=500)
    source: Literal["SELF_REPORTED"] = "SELF_REPORTED"


class CameraSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: int = Field(ge=0, le=30)
    status: Literal["COMPLETED", "INCOMPLETE", "CANCELLED"]
    camera_facing: Literal["FRONT"] = "FRONT"
    capture_quality: Literal["GOOD", "FAIR", "POOR", "INSUFFICIENT_DATA"]
    valid_frame_ratio: FiniteFloat = Field(ge=0, le=1)
    face_presence_ratio: FiniteFloat = Field(ge=0, le=1)
    multiple_face_frames: int = Field(default=0, ge=0)
    raw_video_retained: Literal[False] = False
    source: Literal["CAMERA_OBSERVED"] = "CAMERA_OBSERVED"

    @model_validator(mode="after")
    def completed_session_has_valid_duration(self) -> CameraSessionCreate:
        if self.status == "COMPLETED" and self.duration_seconds != 30:
            raise ValueError("A completed camera assessment must last 30 seconds.")
        if self.completed_at and self.completed_at < self.started_at:
            raise ValueError("The completion time cannot precede the start time.")
        return self


class CameraFeaturesCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    face_presence_ratio: FiniteFloat = Field(ge=0, le=1)
    face_position_stability: Literal["STABLE", "VARIABLE", "INSUFFICIENT_DATA"]
    head_movement_magnitude: FiniteFloat | None = Field(default=None, ge=0)
    head_movement_variability: FiniteFloat | None = Field(default=None, ge=0)
    head_orientation_range: FiniteFloat | None = Field(default=None, ge=0)
    eye_observation_summary: dict[str, Any] | None = None
    smile_observation_summary: dict[str, Any] | None = None
    facial_feature_movement: FiniteFloat | None = Field(default=None, ge=0)
    face_detected_frames: int = Field(default=0, ge=0)
    valid_frames: int = Field(default=0, ge=0)
    invalid_frames: int = Field(default=0, ge=0)
    poor_lighting_frames: int = Field(default=0, ge=0)
    face_out_of_frame_frames: int = Field(default=0, ge=0)
    capture_quality: Literal["GOOD", "FAIR", "POOR", "INSUFFICIENT_DATA"]
    feature_schema_version: str = Field(min_length=1, max_length=40)
    source: Literal["CAMERA_OBSERVED"] = "CAMERA_OBSERVED"


class SleepRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    start_time: datetime
    end_time: datetime
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    quality_rating: int | None = Field(default=None, ge=1, le=5)
    interruptions: int | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=500)
    source: Literal["SELF_REPORTED", "WATCH_DERIVED", "HEALTH_CONNECT"] = "SELF_REPORTED"
    source_id: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_sleep_interval(self) -> SleepRecordCreate:
        seconds = (self.end_time - self.start_time).total_seconds()
        if seconds <= 0 or seconds > 24 * 60 * 60:
            raise ValueError("Sleep times must define an interval within 24 hours.")
        calculated = round(seconds / 60)
        if self.duration_minutes is not None and abs(self.duration_minutes - calculated) > 1:
            raise ValueError("Sleep duration must match the recorded start and end times.")
        self.duration_minutes = calculated
        return self


class RecoveryRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    recovery_state: Literal["GOOD", "MODERATE", "LOW", "INSUFFICIENT_DATA"]
    supporting_factors: dict[str, Any] = Field(default_factory=dict)
    calculation_version: str = Field(min_length=1, max_length=40)
    source: Literal["CALCULATED"] = "CALCULATED"


class WellbeingReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    report_type: Literal[
        "WELLBEING_CHECKIN",
        "CAMERA_WELLBEING",
        "SLEEP",
        "RECOVERY",
        "WEEKLY_WELLBEING",
        "MONTHLY_WELLBEING",
    ]
    report_data: dict[str, Any]
    source_provenance: list[WellbeingSource]
    limitations: list[str] = Field(min_length=1, max_length=20)


class WellbeingIdResponse(BaseModel):
    id: UUID
