from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator
from uuid import UUID


class SensorQuality(StrEnum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    POOR = "POOR"
    INSUFFICIENT = "INSUFFICIENT"


class SessionAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID


class BaselineComparison(StrEnum):
    PERSONAL_BASELINE_NOT_AVAILABLE = "PERSONAL_BASELINE_NOT_AVAILABLE"
    STABLE = "STABLE"
    IMPROVED = "IMPROVED"
    DEVIATION_DETECTED = "DEVIATION_DETECTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class MovementAnomalyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_timestamp: int = Field(ge=0)
    anomaly_type: Literal["UNUSUAL_MOVEMENT_PATTERN"]
    severity: Literal["LOW", "MODERATE", "HIGH"]
    baseline_deviation: FiniteFloat | None = Field(default=None, ge=0, le=100)
    model_name: str | None = Field(default=None, max_length=100)
    model_version: str | None = Field(default=None, max_length=80)
    requires_review: bool = False


class MovementEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: int = Field(ge=0)
    event_type: Literal[
        "REP_COMPLETED",
        "QUALITY_CHANGED",
        "FATIGUE_SIGNAL_CHANGED",
        "ANOMALY_DETECTED",
        "EXERCISE_CHANGED",
        "SENSOR_QUALITY_DEGRADED",
    ]
    severity: Literal["LOW", "MODERATE", "HIGH"]
    description: str = Field(min_length=1, max_length=240)
    source: Literal["LIVE_SENSOR", "SIMULATION", "MANUAL", "CALCULATED", "MODEL_INFERRED"]


class MovementIntelligenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_recognition_status: Literal["RECOGNIZED", "UNKNOWN", "INSUFFICIENT_DATA", "MODEL_UNAVAILABLE"]
    recognized_exercise: Literal[
        "REST", "WALK", "SQUAT", "SIT_TO_STAND", "LEG_RAISE", "CALF_RAISE",
        "HAMSTRING_BRIDGE", "BALANCE", "UNKNOWN",
    ] | None = None
    prediction_source: Literal["MODEL_INFERRED", "DETERMINISTIC", "MANUAL"] | None = None
    model_name: str | None = Field(default=None, max_length=100)
    model_version: str | None = Field(default=None, max_length=80)
    feature_schema_version: str | None = Field(default=None, max_length=80)
    prediction_timestamp: int | None = Field(default=None, ge=0)
    consistency: Literal["STABLE", "MODERATE", "VARIABLE", "INCONSISTENT", "INSUFFICIENT_DATA"]
    sensor_quality_status: SensorQuality
    baseline_status: BaselineComparison
    calculation_version: str = Field(min_length=1, max_length=40)
    anomalies: list[MovementAnomalyInput] = Field(default_factory=list, max_length=50)
    events: list[MovementEventInput] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def prediction_has_provenance(self) -> MovementIntelligenceInput:
        if self.exercise_recognition_status == "RECOGNIZED":
            if self.recognized_exercise in {None, "UNKNOWN"}:
                raise ValueError("Recognized exercise status requires a known exercise.")
            if self.prediction_source == "MODEL_INFERRED" and not (
                self.model_name and self.model_version and self.feature_schema_version and self.prediction_timestamp is not None
            ):
                raise ValueError("Model-derived exercise recognition requires model, feature-schema and prediction timestamp provenance.")
        if self.prediction_source == "MODEL_INFERRED" and self.model_version is None:
            raise ValueError("Model-derived movement intelligence requires a model version.")
        return self
